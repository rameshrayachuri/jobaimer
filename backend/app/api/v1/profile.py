"""Profile API — manage user profile, preferences, resume upload."""
import io
from uuid import UUID

import boto3
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.core.config import settings
from app.core.database import get_db

router = APIRouter()
s3 = boto3.client("s3", region_name=settings.AWS_REGION)

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10MB


class PreferencesUpdate(BaseModel):
    target_titles: list[str] | None = None
    preferred_locations: list[str] | None = None
    remote_preference: str | None = None
    target_industries: list[str] | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    excluded_companies: list[str] | None = None
    seniority_level: str | None = None


@router.get("/profile")
async def get_profile(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute("""
        SELECT full_name, email, phone, location, linkedin_url, github_url,
               target_titles, preferred_locations, remote_preference,
               salary_min, salary_max, excluded_companies, seniority_level,
               agent_status, last_cycle_at, next_cycle_at, total_yoe
        FROM applicant_profiles WHERE user_id = $1
    """, [str(current_user.id)])
    row = result.fetchone()
    if not row:
        return {"user_id": str(current_user.id), "onboarding_complete": False}

    cols = ["full_name","email","phone","location","linkedin_url","github_url",
            "target_titles","preferred_locations","remote_preference",
            "salary_min","salary_max","excluded_companies","seniority_level",
            "agent_status","last_cycle_at","next_cycle_at","total_yoe"]
    data = dict(zip(cols, row))
    data["user_id"] = str(current_user.id)
    data["onboarding_complete"] = bool(data.get("agent_status"))
    return data


@router.put("/profile")
async def update_profile(
    body: PreferencesUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(400, "No fields to update")

    set_clause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(fields.keys()))
    await db.execute(
        f"UPDATE applicant_profiles SET {set_clause}, updated_at = NOW() WHERE user_id = $1",
        [str(current_user.id)] + list(fields.values()),
    )
    return {"updated": True, "fields": list(fields.keys())}


@router.post("/profile/resume")
async def upload_resume(
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload master resume (PDF or DOCX). Parses and stores structured data."""
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(400, "Only PDF and DOCX files are accepted")

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(400, "File too large. Maximum 10MB.")

    # Extract text
    from app.services.resume_parser import extract_text, parse_resume_with_claude
    text = await extract_text(content, file.content_type)
    parsed = await parse_resume_with_claude(text)

    # Store in S3
    import time
    from datetime import datetime, timezone
    s3_key = f"resumes/master/{current_user.id}/master_{int(time.time())}.pdf"
    s3.put_object(
        Bucket=settings.S3_RESUME_BUCKET,
        Key=s3_key,
        Body=content,
        ContentType="application/pdf",
        ServerSideEncryption="AES256",
    )

    # Save resume_version to DB
    result = await db.execute("""
        INSERT INTO resume_versions
            (user_id, version_type, s3_bucket, s3_key, file_name, file_size_bytes,
             parsed_data, version_label, last_accessed_at)
        VALUES ($1, 'master', $2, $3, $4, $5, $6, 'master', NOW())
        RETURNING id
    """, [
        str(current_user.id), settings.S3_RESUME_BUCKET, s3_key,
        file.filename or "resume.pdf", len(content),
        str(parsed),
    ])
    rv_id = result.fetchone()[0]

    # Update applicant_profile with extracted data
    await db.execute("""
        INSERT INTO applicant_profiles
            (user_id, full_name, email, total_yoe, seniority_level,
             technical_skills, tools, summary)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
        ON CONFLICT (user_id) DO UPDATE SET
            full_name = EXCLUDED.full_name,
            total_yoe = EXCLUDED.total_yoe,
            seniority_level = EXCLUDED.seniority_level,
            technical_skills = EXCLUDED.technical_skills,
            tools = EXCLUDED.tools,
            summary = EXCLUDED.summary,
            updated_at = NOW()
    """, [
        str(current_user.id),
        parsed.get("contact", {}).get("name", ""),
        parsed.get("contact", {}).get("email", ""),
        parsed.get("total_years_experience"),
        _infer_seniority(parsed.get("total_years_experience", 0)),
        parsed.get("skills", {}).get("technical", []),
        parsed.get("skills", {}).get("tools", []),
        parsed.get("summary", ""),
    ])

    return {
        "resume_version_id": str(rv_id),
        "parsed_data": parsed,
        "message": "Resume parsed successfully",
    }


def _infer_seniority(yoe: float) -> str:
    if yoe is None:
        return "mid"
    if yoe < 2:
        return "entry"
    if yoe < 5:
        return "mid"
    if yoe < 8:
        return "senior"
    if yoe < 12:
        return "staff"
    return "director"
