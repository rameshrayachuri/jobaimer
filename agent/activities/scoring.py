"""Scoring activity — fast ATS pre-screen before full tailor."""
from temporalio import activity


@activity.defn
async def quick_score_job(user_id: str, job_id: str) -> float:
    """Fast keyword-match score. Returns 0-100. No Claude call."""
    from app.core.database import AsyncSessionLocal
    from rapidfuzz import fuzz

    async with AsyncSessionLocal() as db:
        result = await db.execute("""
            SELECT jp.title, jp.job_description, jp.company,
                   ap.technical_skills, ap.target_titles, ap.total_yoe
            FROM job_postings jp, applicant_profiles ap
            WHERE jp.id = $1 AND ap.user_id = $2
        """, [job_id, user_id])
        row = result.fetchone()

    if not row:
        return 0.0

    jd_title, jd_text, company, skills, target_titles, yoe = row
    jd_lower = (jd_text or "").lower()

    score = 0.0

    # Title match (30 pts)
    if target_titles:
        title_scores = [fuzz.partial_ratio(t.lower(), jd_title.lower()) for t in target_titles]
        score += 0.30 * (max(title_scores) / 100.0 * 100)

    # Skills match (50 pts)
    if skills:
        matched = sum(1 for s in skills if s.lower() in jd_lower)
        score += 0.50 * min(100, matched / max(len(skills), 1) * 100 * 2)

    # YOE plausibility (20 pts)
    import re
    yoe_mentions = re.findall(r'(\d+)\s*\+?\s*year', jd_lower)
    if yoe_mentions and yoe:
        required_yoe = int(yoe_mentions[0])
        if yoe >= required_yoe:
            score += 20.0
        elif yoe >= required_yoe * 0.7:
            score += 10.0

    # Already applied?
    async with AsyncSessionLocal() as db:
        existing = await db.execute("""
            SELECT id FROM applications
            WHERE user_id = $1 AND job_posting_id = $2 AND deleted_at IS NULL
        """, [user_id, job_id])
        if existing.fetchone():
            return 0.0  # Block duplicate — enforced by DB constraint too

    # Store quick_score for analytics
    async with AsyncSessionLocal() as db:
        await db.execute("""
            INSERT INTO applications (user_id, job_posting_id, status, quick_score)
            VALUES ($1, $2, 'discovered', $3)
            ON CONFLICT DO NOTHING
        """, [user_id, job_id, round(score, 2)])
        await db.commit()

    return round(score, 2)
