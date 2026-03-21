"""Job discovery activity — scrapes portals via Playwright."""
import asyncio
import json
from typing import Any
from temporalio import activity
from playwright.async_api import async_playwright


@activity.defn
async def discover_jobs(user_id: str, max_portals: int) -> list[dict[str, Any]]:
    """Discover matching jobs for user across portals."""
    from app.core.config import settings
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        profile = await db.execute("""
            SELECT target_titles, preferred_locations, remote_preference,
                   target_industries, excluded_companies, salary_min
            FROM applicant_profiles WHERE user_id = $1
        """, [user_id])
        row = profile.fetchone()

    if not row:
        return []

    target_titles, locations, remote_pref, industries, excluded, salary_min = row

    activity.logger.info(f"Discovering jobs for {user_id} — titles={target_titles}")

    portals_enabled = ["linkedin", "indeed", "glassdoor", "ziprecruiter"][:max_portals]
    discovered: list[dict] = []

    # Import portal scrapers
    for portal_name in portals_enabled:
        try:
            portal_jobs = await _scrape_portal(
                portal_name, target_titles or [], locations or [],
                remote_pref or "any", excluded or [], salary_min
            )
            discovered.extend(portal_jobs)
        except Exception as e:
            activity.logger.error(f"Portal {portal_name} failed: {e}")

    # Deduplicate and store in DB
    stored = await _store_jobs(discovered)
    activity.logger.info(f"Discovered {len(stored)} new jobs for {user_id}")
    return stored


async def _scrape_portal(
    portal: str,
    titles: list[str],
    locations: list[str],
    remote_pref: str,
    excluded_companies: list[str],
    salary_min: int | None,
) -> list[dict]:
    """Scrape a portal for matching jobs."""
    results = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage",
                  "--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720},
        )

        page = await context.new_page()

        for title in titles[:3]:  # Cap per title to avoid rate limits
            try:
                jobs = await _search_portal(page, portal, title, locations, remote_pref)
                for j in jobs:
                    if j.get("company", "").lower() not in [
                        e.lower() for e in excluded_companies
                    ]:
                        j["portal"] = portal
                        results.append(j)
            except Exception as e:
                activity.logger.warning(f"Search failed for {title} on {portal}: {e}")

        await browser.close()

    return results


async def _search_portal(page, portal: str, title: str,
                          locations: list[str], remote_pref: str) -> list[dict]:
    """Portal-specific search logic."""
    jobs = []
    location = locations[0] if locations else ""
    if remote_pref in ("remote_only", "remote_first"):
        location = "Remote"

    if portal == "linkedin":
        q = title.replace(" ", "%20")
        url = f"https://www.linkedin.com/jobs/search/?keywords={q}&location={location}&f_TPR=r86400"
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)
        cards = await page.query_selector_all(".jobs-search__results-list li")
        for card in cards[:10]:
            try:
                t = await card.query_selector("h3.base-search-card__title")
                c = await card.query_selector("h4.base-search-card__subtitle")
                a = await card.query_selector("a.base-card__full-link")
                if t and c and a:
                    jobs.append({
                        "title": (await t.inner_text()).strip(),
                        "company": (await c.inner_text()).strip(),
                        "location": location,
                        "apply_url": await a.get_attribute("href"),
                        "portal_job_id": (await a.get_attribute("href") or "").split("?")[0].split("-")[-1],
                        "job_description": "",
                    })
            except Exception:
                pass

    elif portal == "indeed":
        q = title.replace(" ", "+")
        url = f"https://www.indeed.com/jobs?q={q}&l={location}"
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)
        cards = await page.query_selector_all("div.job_seen_beacon")
        for card in cards[:10]:
            try:
                t = await card.query_selector("h2.jobTitle span")
                c = await card.query_selector("span.companyName")
                a = await card.query_selector("a.jcs-JobTitle")
                if t and c and a:
                    href = await a.get_attribute("href")
                    jobs.append({
                        "title": (await t.inner_text()).strip(),
                        "company": (await c.inner_text()).strip(),
                        "location": location,
                        "apply_url": f"https://www.indeed.com{href}" if href else "",
                        "portal_job_id": href.split("jk=")[-1].split("&")[0] if href else "",
                        "job_description": "",
                    })
            except Exception:
                pass

    return jobs


async def _store_jobs(jobs: list[dict]) -> list[dict]:
    """Store discovered jobs in DB, return IDs for new/existing."""
    if not jobs:
        return []
    from app.core.database import AsyncSessionLocal
    stored = []
    async with AsyncSessionLocal() as db:
        for j in jobs:
            if not j.get("title") or not j.get("company") or not j.get("apply_url"):
                continue
            try:
                result = await db.execute("""
                    INSERT INTO job_postings (portal, portal_job_id, title, company, location,
                                             apply_url, job_description, posted_at)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,NOW())
                    ON CONFLICT (portal, portal_job_id) DO UPDATE
                        SET scraped_at = NOW()
                    RETURNING id, title, company
                """, [
                    j.get("portal", "unknown"),
                    j.get("portal_job_id", "")[:100],
                    j["title"][:200],
                    j["company"][:200],
                    j.get("location", "")[:200],
                    j["apply_url"][:1000],
                    j.get("job_description", "")[:10000],
                ])
                row = result.fetchone()
                if row:
                    stored.append({"id": str(row[0]), "title": row[1], "company": row[2]})
            except Exception as e:
                activity.logger.warning(f"Failed to store job: {e}")
        await db.commit()
    return stored
