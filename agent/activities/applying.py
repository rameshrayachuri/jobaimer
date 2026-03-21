"""Apply activity — submits application via Playwright and takes screenshot."""
import asyncio
import io
import time
from temporalio import activity


@activity.defn
async def apply_to_job(user_id: str, job_id: str, resume_version_id: str) -> dict:
    """Apply to job via Playwright. Returns success/failure + confirmation details."""
    from app.core.config import settings
    from app.core.database import AsyncSessionLocal
    import boto3
    from playwright.async_api import async_playwright

    s3 = boto3.client("s3", region_name=settings.AWS_REGION)

    async with AsyncSessionLocal() as db:
        result = await db.execute("""
            SELECT jp.apply_url, jp.portal, jp.title, jp.company,
                   ap.full_name, ap.email, ap.phone, ap.location,
                   ap.linkedin_url, rv.s3_key, rv.s3_bucket
            FROM job_postings jp
            JOIN applicant_profiles ap ON ap.user_id = $1
            JOIN resume_versions rv ON rv.id = $2
            WHERE jp.id = $3
        """, [user_id, resume_version_id, job_id])
        row = result.fetchone()

        await db.execute("""
            UPDATE applications SET status = 'applying' WHERE user_id = $1 AND job_posting_id = $2
        """, [user_id, job_id])
        await db.commit()

    if not row:
        return {"success": False, "failure_reason": "Missing job or profile data"}

    apply_url, portal, job_title, company, full_name, email, phone, location, linkedin, rv_s3_key, rv_bucket = row

    # Download tailored resume PDF from S3 to temp file
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        s3.download_file(rv_bucket, rv_s3_key, f.name)
        resume_path = f.name

    try:
        result = await _apply_playwright(
            apply_url=apply_url,
            portal=portal,
            full_name=full_name or "",
            email=email or "",
            phone=phone or "",
            location=location or "",
            linkedin=linkedin or "",
            resume_path=resume_path,
            user_id=user_id,
            job_id=job_id,
        )
        return result
    finally:
        os.unlink(resume_path)


async def _apply_playwright(
    apply_url: str,
    portal: str,
    full_name: str,
    email: str,
    phone: str,
    location: str,
    linkedin: str,
    resume_path: str,
    user_id: str,
    job_id: str,
) -> dict:
    from app.core.config import settings
    import boto3

    s3 = boto3.client("s3", region_name=settings.AWS_REGION)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=settings.BROWSER_HEADLESS,
            args=["--no-sandbox", "--disable-dev-shm-usage",
                  "--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        page = await context.new_page()

        try:
            await page.goto(apply_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            # Generic "Easy Apply" form strategy — detect and fill common fields
            filled = await _fill_application_form(page, full_name, email, phone, location, linkedin, resume_path)

            if not filled:
                # Can't auto-apply — flag for manual review
                screenshot = await page.screenshot(full_page=False)
                s3_key = f"screenshots/{user_id}/{job_id}_{int(time.time())}.png"
                s3.put_object(Bucket=settings.S3_RESUME_BUCKET, Key=s3_key,
                              Body=screenshot, ContentType="image/png",
                              ServerSideEncryption="AES256")
                return {
                    "success": False,
                    "failure_reason": "manual_apply_required",
                    "manual_apply_url": apply_url,
                    "screenshot_path": s3_key,
                }

            # Take confirmation screenshot
            await asyncio.sleep(2)
            screenshot = await page.screenshot(full_page=False)
            s3_key = f"screenshots/{user_id}/{job_id}_{int(time.time())}.png"
            s3.put_object(Bucket=settings.S3_RESUME_BUCKET, Key=s3_key,
                          Body=screenshot, ContentType="image/png",
                          ServerSideEncryption="AES256")

            # Try to extract confirmation ID from page
            confirmation_id = await _extract_confirmation(page)

            return {
                "success": True,
                "confirmation_id": confirmation_id,
                "screenshot_path": s3_key,
            }

        except Exception as e:
            activity.logger.error(f"Playwright error: {e}")
            return {"success": False, "failure_reason": f"browser_error: {str(e)[:100]}"}
        finally:
            await browser.close()


async def _fill_application_form(page, full_name, email, phone, location, linkedin, resume_path):
    """Try to auto-fill common application form fields. Returns True if submitted."""
    filled_any = False

    # Name field
    name_selectors = ["input[name*='name']", "input[placeholder*='name' i]",
                      "input[id*='name' i]", "input[autocomplete='name']"]
    for sel in name_selectors:
        try:
            el = page.locator(sel).first
            if await el.is_visible(timeout=1000):
                await el.fill(full_name)
                filled_any = True
                break
        except Exception:
            pass

    # Email field
    email_selectors = ["input[type='email']", "input[name*='email' i]", "input[id*='email' i]"]
    for sel in email_selectors:
        try:
            el = page.locator(sel).first
            if await el.is_visible(timeout=1000):
                await el.fill(email)
                filled_any = True
                break
        except Exception:
            pass

    # Phone field
    phone_selectors = ["input[type='tel']", "input[name*='phone' i]"]
    for sel in phone_selectors:
        try:
            el = page.locator(sel).first
            if await el.is_visible(timeout=1000):
                await el.fill(phone)
                break
        except Exception:
            pass

    # Resume file upload
    file_selectors = ["input[type='file']"]
    for sel in file_selectors:
        try:
            el = page.locator(sel).first
            if await el.is_visible(timeout=1000):
                await el.set_input_files(resume_path)
                break
        except Exception:
            pass

    # Submit button
    if filled_any:
        submit_selectors = [
            "button[type='submit']", "button:text-matches('submit', 'i')",
            "button:text-matches('apply', 'i')", "input[type='submit']"
        ]
        for sel in submit_selectors:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=2000):
                    await btn.click()
                    await asyncio.sleep(2)
                    return True
            except Exception:
                pass

    return False


async def _extract_confirmation(page) -> str | None:
    """Try to extract a confirmation/application ID from thank-you page."""
    patterns = [
        r'[A-Z0-9]{6,}',
        r'application.*?(?:id|#|number)[:\s]+([A-Z0-9\-]+)',
        r'reference[:\s]+([A-Z0-9\-]+)',
    ]
    import re
    try:
        body = await page.inner_text("body")
        for pattern in patterns:
            match = re.search(pattern, body, re.IGNORECASE)
            if match:
                return match.group(0)[:50]
    except Exception:
        pass
    return None
