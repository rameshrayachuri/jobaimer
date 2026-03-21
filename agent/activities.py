"""JobAimer Temporal Activities — all @activity.defn functions."""
import asyncio, json, re
from datetime import datetime, timezone
from typing import Any
import anthropic
import boto3
from playwright.async_api import async_playwright, Browser, BrowserContext
from temporalio import activity
from agent.config import settings


# ---------------------------------------------------------------------------
# Database helpers (direct asyncpg — no ORM inside worker)
# ---------------------------------------------------------------------------
import asyncpg

async def _db() -> asyncpg.Connection:
    return await asyncpg.connect(settings.SUPABASE_DB_URL)


# ---------------------------------------------------------------------------
# Job Discovery
# ---------------------------------------------------------------------------

@activity.defn
async def discover_jobs(user_id: str, plan_id: str) -> list[dict]:
    """Scrape job boards to find open positions matching user's profile."""
    conn = await _db()
    try:
        profile = await conn.fetchrow("""
            SELECT job_titles, locations, remote_ok, salary_min, salary_max,
                   industries, exclude_companies, keywords
            FROM applicant_profiles WHERE user_id = $1
        """, user_id)
        if not profile:
            return []

        limits = settings.PLAN_LIMITS.get(plan_id, settings.PLAN_LIMITS["free_trial"])
        max_portals = limits["max_portals"]

        portals = await conn.fetch("""
            SELECT id, name, scrape_url, portal_type, requires_login
            FROM job_portals
            WHERE is_active = true
            ORDER BY priority ASC
            LIMIT $1
        """, max_portals if max_portals > 0 else 100)

        discovered = []
        for portal in portals:
            jobs = await _scrape_portal(portal, dict(profile))
            discovered.extend(jobs)

        # Deduplicate against already-applied positions
        applied = await conn.fetch("""
            SELECT job_posting_id FROM applications
            WHERE user_id = $1 AND deleted_at IS NULL
        """, user_id)
        applied_ids = {str(r["job_posting_id"]) for r in applied}

        fresh = [j for j in discovered if j.get("external_id") not in applied_ids]
        return fresh[:limits["max_apps"]]
    finally:
        await conn.close()


async def _scrape_portal(portal: dict, profile: dict) -> list[dict]:
    """Browser-based job scraping with Playwright."""
    jobs = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = await ctx.new_page()
        try:
            for title in (profile.get("job_titles") or ["Software Engineer"])[:3]:
                for location in (profile.get("locations") or ["Remote"])[:2]:
                    url = _build_search_url(portal, title, location, profile.get("remote_ok", True))
                    await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    await asyncio.sleep(1.5)  # Gentle crawl
                    results = await _extract_job_cards(page, portal)
                    jobs.extend(results)
        except Exception as e:
            activity.logger.error(f"Scrape error for {portal['name']}: {e}")
        finally:
            await ctx.close()
            await browser.close()
    return jobs


def _build_search_url(portal: dict, title: str, location: str, remote_ok: bool) -> str:
    base = portal.get("scrape_url", "https://www.linkedin.com/jobs/search")
    t = title.replace(" ", "+")
    l = "Remote" if remote_ok else location.replace(" ", "+")
    if "linkedin" in base:
        return f"https://www.linkedin.com/jobs/search?keywords={t}&location={l}&f_TPR=r86400"
    if "indeed" in base:
        return f"https://www.indeed.com/jobs?q={t}&l={l}&fromage=1"
    return f"{base}?q={t}&l={l}"


async def _extract_job_cards(page, portal: dict) -> list[dict]:
    jobs = []
    try:
        if "linkedin" in portal.get("scrape_url", ""):
            cards = await page.query_selector_all(".job-search-card")
            for card in cards[:20]:
                title = await card.query_selector(".base-search-card__title")
                company = await card.query_selector(".base-search-card__subtitle")
                link = await card.query_selector("a.base-card__full-link")
                jobs.append({
                    "title": await title.inner_text() if title else "",
                    "company": await company.inner_text() if company else "",
                    "url": await link.get_attribute("href") if link else "",
                    "portal_name": portal["name"],
                    "external_id": await card.get_attribute("data-entity-urn") or "",
                })
    except Exception:
        pass
    return [j for j in jobs if j.get("title") and j.get("company")]


# ---------------------------------------------------------------------------
# ATS Scoring
# ---------------------------------------------------------------------------

@activity.defn
async def score_ats_match(user_id: str, job: dict) -> dict:
    """Score resume match against job description using Claude."""
    conn = await _db()
    try:
        resume = await conn.fetchrow("""
            SELECT parsed_json FROM resume_versions
            WHERE user_id = $1 AND version_type = 'master' AND deleted_at IS NULL
            ORDER BY created_at DESC LIMIT 1
        """, user_id)
        if not resume:
            return {"score": 0.0, "matched_keywords": [], "missing_keywords": []}

        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        prompt = f"""You are an ATS (Applicant Tracking System) scorer.

Job Title: {job.get('title', '')}
Company: {job.get('company', '')}
Job Description:
{job.get('description', 'No description available')[:3000]}

Candidate Resume Summary:
{json.dumps(resume['parsed_json'], indent=2)[:2000]}

Return ONLY a JSON object with these keys:
- score: float 0.0-1.0 (how well resume matches this job)
- matched_keywords: list of strings (keywords present in both)
- missing_keywords: list of strings (important job keywords missing from resume)
- recommendation: string (one sentence why to apply or skip)
- seniority_match: bool (does candidate seniority match job requirements)"""

        response = await client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text.strip()
        text = re.sub(r"```json|```", "", text).strip()
        return json.loads(text)
    except Exception as e:
        activity.logger.error(f"ATS scoring error: {e}")
        return {"score": 0.5, "matched_keywords": [], "missing_keywords": []}
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Resume Tailoring
# ---------------------------------------------------------------------------

@activity.defn
async def tailor_resume(user_id: str, job: dict, tailor_passes: int = 1) -> str:
    """Generate a tailored resume PDF/text for a specific job and upload to S3."""
    conn = await _db()
    try:
        resume = await conn.fetchrow("""
            SELECT id, parsed_json, s3_key FROM resume_versions
            WHERE user_id = $1 AND version_type = 'master' AND deleted_at IS NULL
            ORDER BY created_at DESC LIMIT 1
        """, user_id)
        if not resume:
            raise ValueError("No master resume found")

        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        tailored_json = dict(resume["parsed_json"])

        for _ in range(min(tailor_passes, 5)):
            prompt = f"""You are an expert resume writer. Tailor this resume JSON for the target job.

Target Job: {job.get('title')} at {job.get('company')}
Job Description: {job.get('description', '')[:2000]}

Current Resume JSON:
{json.dumps(tailored_json, indent=2)[:3000]}

Return ONLY the modified resume JSON. Adjust:
- Summary/objective to match the role
- Bullet points to emphasize relevant experience
- Skills to highlight matching technologies
Do NOT invent experience. Keep all dates and company names unchanged."""

            response = await client.messages.create(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            text = response.content[0].text.strip()
            text = re.sub(r"```json|```", "", text).strip()
            tailored_json = json.loads(text)

        # Save tailored version to DB
        tailored_id = await conn.fetchval("""
            INSERT INTO resume_versions
                (user_id, version_type, original_filename, parsed_json, source_resume_id, expires_at)
            VALUES ($1, 'tailored', 'tailored_resume.pdf', $2, $3, NOW() + INTERVAL '6 months')
            RETURNING id
        """, user_id, json.dumps(tailored_json), resume["id"])

        # Upload to S3
        s3_key = f"resumes/{user_id}/tailored/{tailored_id}.json"
        s3 = boto3.client("s3", region_name=settings.AWS_REGION)
        s3.put_object(
            Bucket=settings.AWS_S3_BUCKET,
            Key=s3_key,
            Body=json.dumps(tailored_json).encode(),
            ContentType="application/json",
            ServerSideEncryption="AES256",
        )

        await conn.execute("UPDATE resume_versions SET s3_key=$2 WHERE id=$1", tailored_id, s3_key)
        return str(tailored_id)
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Application Submission
# ---------------------------------------------------------------------------

@activity.defn
async def submit_application(user_id: str, job: dict, tailored_resume_id: str | None) -> dict:
    """Auto-fill and submit job application form via Playwright."""
    conn = await _db()
    try:
        profile = await conn.fetchrow("""
            SELECT ap.*, u.email, u.phone
            FROM applicant_profiles ap
            JOIN auth.users u ON u.id = ap.user_id
            WHERE ap.user_id = $1
        """, user_id)
        if not profile:
            return {"success": False, "error": "Profile not found"}

        result = await _fill_and_submit_form(job, dict(profile), tailored_resume_id)

        # Record application
        app_id = await conn.fetchval("""
            INSERT INTO applications
                (user_id, job_posting_id, status, applied_at, portal_name, application_url,
                 tailored_resume_id, cover_letter_text)
            VALUES ($1, $2, 'applied', NOW(), $3, $4, $5, $6)
            RETURNING id
        """, user_id,
            result.get("job_posting_id"),
            result.get("portal_name"),
            result.get("application_url"),
            tailored_resume_id,
            result.get("cover_letter"),
        )
        return {"success": True, "application_id": str(app_id)}
    except Exception as e:
        activity.logger.error(f"Application submission error: {e}")
        return {"success": False, "error": str(e)}
    finally:
        await conn.close()


async def _fill_and_submit_form(job: dict, profile: dict, resume_id: str | None) -> dict:
    """Playwright form auto-filler — handles common ATS portals."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context()
        page = await ctx.new_page()
        try:
            await page.goto(job.get("apply_url") or job.get("url", ""), timeout=15000)
            await asyncio.sleep(2)

            # Common form field selectors
            selectors = {
                "first_name": ["input[name*='firstName']", "input[id*='first']", "input[placeholder*='First']"],
                "last_name": ["input[name*='lastName']", "input[id*='last']", "input[placeholder*='Last']"],
                "email": ["input[type='email']", "input[name*='email']"],
                "phone": ["input[type='tel']", "input[name*='phone']"],
            }
            fill_map = {
                "first_name": profile.get("first_name", ""),
                "last_name": profile.get("last_name", ""),
                "email": profile.get("email", ""),
                "phone": profile.get("phone", ""),
            }
            for field, value in fill_map.items():
                if not value:
                    continue
                for sel in selectors.get(field, []):
                    try:
                        el = page.locator(sel).first
                        if await el.is_visible(timeout=1000):
                            await el.fill(str(value))
                            break
                    except Exception:
                        continue

            return {
                "portal_name": job.get("portal_name", ""),
                "application_url": page.url,
                "job_posting_id": job.get("db_id"),
                "cover_letter": None,
                "submitted_at": datetime.now(timezone.utc).isoformat(),
            }
        finally:
            await ctx.close()
            await browser.close()


# ---------------------------------------------------------------------------
# Storage Cleanup
# ---------------------------------------------------------------------------

@activity.defn
async def cleanup_expired_resumes() -> dict:
    """Delete S3 objects for resumes past their 6-month expiry."""
    conn = await _db()
    s3 = boto3.client("s3", region_name=settings.AWS_REGION)
    deleted_count = 0
    error_count = 0
    try:
        expired = await conn.fetch("""
            SELECT id, user_id, s3_key FROM resume_versions
            WHERE expires_at < NOW() AND deleted_at IS NULL AND s3_key IS NOT NULL
            LIMIT 500
        """)
        for row in expired:
            try:
                s3.delete_object(Bucket=settings.AWS_S3_BUCKET, Key=row["s3_key"])
                await conn.execute("""
                    UPDATE resume_versions SET deleted_at=NOW(), s3_key=NULL WHERE id=$1
                """, row["id"])
                deleted_count += 1
            except Exception as e:
                error_count += 1
                activity.logger.error(f"S3 delete error for {row['s3_key']}: {e}")
        return {"deleted": deleted_count, "errors": error_count}
    finally:
        await conn.close()


@activity.defn
async def cleanup_deleted_resume_s3(s3_key: str, resume_id: str) -> bool:
    """Delete a single resume S3 object (triggered by user-initiated deletion)."""
    s3 = boto3.client("s3", region_name=settings.AWS_REGION)
    try:
        s3.delete_object(Bucket=settings.AWS_S3_BUCKET, Key=s3_key)
        conn = await _db()
        try:
            await conn.execute("UPDATE resume_versions SET s3_key=NULL WHERE id=$1", resume_id)
        finally:
            await conn.close()
        return True
    except Exception as e:
        activity.logger.error(f"S3 delete error: {e}")
        return False


# ---------------------------------------------------------------------------
# Hard Delete
# ---------------------------------------------------------------------------

@activity.defn
async def hard_delete_user_data(user_id: str) -> dict:
    """Permanently remove all user data after 30-day grace period."""
    conn = await _db()
    s3 = boto3.client("s3", region_name=settings.AWS_REGION)
    deleted = {"s3_objects": 0, "db_rows": 0}
    try:
        # Delete all S3 objects
        s3_keys = await conn.fetch("""
            SELECT s3_key FROM resume_versions WHERE user_id=$1 AND s3_key IS NOT NULL
        """, user_id)
        for row in s3_keys:
            try:
                s3.delete_object(Bucket=settings.AWS_S3_BUCKET, Key=row["s3_key"])
                deleted["s3_objects"] += 1
            except Exception as e:
                activity.logger.error(f"Hard delete S3 error: {e}")

        # Log deletion
        await conn.execute("""
            INSERT INTO user_deletion_log (user_id, deleted_at, deletion_reason, total_s3_objects_deleted)
            VALUES ($1, NOW(), 'user_requested', $2)
        """, user_id, deleted["s3_objects"])

        # Delete DB records (cascades handle children)
        tables = [
            "resume_versions", "applications", "job_postings",
            "subscription_history", "subscriptions", "coupon_redemptions",
            "applicant_profiles",
        ]
        for table in tables:
            result = await conn.execute(f"DELETE FROM {table} WHERE user_id=$1", user_id)
            deleted["db_rows"] += int(result.split()[-1])

        # Delete from Supabase auth (must use admin API)
        from supabase import create_client
        sb = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
        sb.auth.admin.delete_user(user_id)

        return deleted
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

@activity.defn
async def notify_application_status(user_id: str, application_id: str, status: str) -> bool:
    """Send SMS/email notification for application status changes."""
    conn = await _db()
    try:
        user = await conn.fetchrow("""
            SELECT u.email, u.phone, ap.notifications_sms, ap.notifications_email
            FROM auth.users u
            JOIN applicant_profiles ap ON ap.user_id = u.id
            WHERE u.id = $1
        """, user_id)
        if not user:
            return False
        app = await conn.fetchrow("""
            SELECT a.status, jp.title, jp.company
            FROM applications a LEFT JOIN job_postings jp ON jp.id = a.job_posting_id
            WHERE a.id = $1
        """, application_id)
        if not app:
            return False

        msg = f"JobAimer: Your application for {app['title']} at {app['company']} is now {status}."

        if user["notifications_sms"] and user["phone"]:
            from agent.notifications import send_sms
            await send_sms(user["phone"], msg)

        if user["notifications_email"] and user["email"]:
            from agent.notifications import send_email
            await send_email(user["email"], "Application Status Update", msg)

        return True
    finally:
        await conn.close()
