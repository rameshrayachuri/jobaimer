"""Resume tailor — AI-powered ATS score optimization per job description."""
import json
from typing import Any
import anthropic
from app.core.config import settings


async def tailor_resume(
    source_resume: dict[str, Any],
    job_title: str,
    company: str,
    job_description: str,
    page_limit: int = 2,
    prior_ats_score: int | None = None,
    missing_keywords: list[str] | None = None,
) -> dict[str, Any]:
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    feedback = ""
    if prior_ats_score and missing_keywords:
        feedback = f"\nPrevious ATS score was {prior_ats_score}. Missing keywords: {missing_keywords}. Incorporate these where truthful."

    prompt = f"""You are an expert ATS resume optimizer.
Rewrite the candidate's resume to maximize ATS match for this job.

STRICT RULES:
1. ONLY use information in the source resume. Never fabricate companies, titles, dates, degrees, or metrics.
2. You MAY reorder bullets, rephrase using JD keywords, expand abbreviations, adjust summary focus.
3. Keep all dates exactly as provided.
4. Maximum {page_limit} pages.{feedback}
5. Output ONLY valid JSON matching the schema — no markdown, no commentary.

JOB: {job_title} at {company}

JOB DESCRIPTION:
{job_description[:3000]}

SOURCE RESUME:
{json.dumps(source_resume, indent=2)[:4000]}

Output this JSON (same as source schema plus these fields):
{{
  ...all source resume fields...,
  "professional_summary": "rewritten summary targeting this role",
  "ats_score": 0-100,
  "ats_reasoning": "brief explanation",
  "keywords_matched": ["list", "of", "matched"],
  "keywords_missing": ["keywords", "not", "in", "resume"],
  "changes_made": ["list of transformations"]
}}"""

    message = await client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=settings.ANTHROPIC_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )

    text = message.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


async def tailor_with_refinement(
    source_resume: dict[str, Any],
    job_title: str,
    company: str,
    job_description: str,
    max_passes: int = 3,
    target_score: int = 85,
    page_limit: int = 2,
) -> dict[str, Any]:
    """Run up to max_passes of tailoring, stopping when target ATS score is reached."""
    result = await tailor_resume(source_resume, job_title, company, job_description, page_limit)

    for _ in range(2, max_passes + 1):
        if result.get("ats_score", 0) >= target_score:
            break
        result = await tailor_resume(
            source_resume, job_title, company, job_description, page_limit,
            prior_ats_score=result.get("ats_score"),
            missing_keywords=result.get("keywords_missing", [])[:10],
        )

    return result
