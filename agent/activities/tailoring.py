"""Tailoring activity — AI resume tailor + PDF generation + S3 storage."""
import io
import json
from temporalio import activity


@activity.defn
async def tailor_and_store_resume(
    user_id: str, job_id: str, claude_passes: int
) -> dict:
    """Tailor resume for this job, save PDF to S3, record in DB."""
    from app.core.config import settings
    from app.core.database import AsyncSessionLocal
    from app.services.resume_tailor import tailor_with_refinement
    from app.services.pdf_builder import build_resume_pdf
    import boto3
    import time

    s3 = boto3.client("s3", region_name=settings.AWS_REGION)

    async with AsyncSessionLocal() as db:
        # Mark status as tailoring
        await db.execute("""
            UPDATE applications SET status = 'tailoring_resume' WHERE user_id = $1 AND job_posting_id = $2
        """, [user_id, job_id])

        # Load job + master resume
        result = await db.execute("""
            SELECT jp.title, jp.company, jp.job_description, jp.apply_url,
                   rv.parsed_data, rv.id as rv_id
            FROM job_postings jp, applicant_profiles ap
            LEFT JOIN resume_versions rv
                ON rv.user_id = ap.user_id AND rv.version_type = 'master' AND rv.deleted_at IS NULL
            WHERE jp.id = $1 AND ap.user_id = $2
            ORDER BY rv.created_at DESC LIMIT 1
        """, [job_id, user_id])
        row = result.fetchone()
        await db.commit()

    if not row or not row[4]:
        return {"success": False, "failure_reason": "No master resume found"}

    title, company, jd, apply_url, parsed_data_raw, master_rv_id = row
    source_resume = json.loads(parsed_data_raw) if isinstance(parsed_data_raw, str) else parsed_data_raw

    activity.logger.info(f"Tailoring resume for {title} @ {company}")

    # Call Claude
    tailored = await tailor_with_refinement(
        source_resume=source_resume,
        job_title=title,
        company=company,
        job_description=jd or "",
        max_passes=claude_passes,
        target_score=85,
    )
    claude_calls = tailored.pop("_claude_calls", 1)

    # Build PDF
    pdf_bytes = await build_resume_pdf(tailored)

    # Upload to S3
    ts = int(time.time())
    safe_company = "".join(c for c in company if c.isalnum() or c == "-")[:30]
    s3_key = f"resumes/tailored/{user_id}/{safe_company}_{ts}.pdf"
    s3.put_object(
        Bucket=settings.S3_RESUME_BUCKET,
        Key=s3_key,
        Body=pdf_bytes,
        ContentType="application/pdf",
        ServerSideEncryption="AES256",
    )

    # Save resume_version
    async with AsyncSessionLocal() as db:
        result = await db.execute("""
            INSERT INTO resume_versions
                (user_id, version_type, job_posting_id, version_label, s3_bucket, s3_key,
                 file_name, file_size_bytes, parsed_data, ats_score, ats_reasoning,
                 keywords_matched, keywords_missing, last_accessed_at)
            VALUES ($1,'tailored',$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,NOW())
            RETURNING id
        """, [
            user_id, job_id,
            f"{safe_company[:20]}_v{ts}",
            settings.S3_RESUME_BUCKET, s3_key,
            f"resume_{safe_company}_{ts}.pdf",
            len(pdf_bytes),
            json.dumps(tailored),
            tailored.get("ats_score"),
            tailored.get("ats_reasoning", ""),
            tailored.get("keywords_matched", []),
            tailored.get("keywords_missing", []),
        ])
        rv_id = result.fetchone()[0]

        # Update application with resume_version_id
        await db.execute("""
            UPDATE applications
            SET resume_version_id = $1, ats_score = $2, status = 'tailored', tailored_at = NOW()
            WHERE user_id = $3 AND job_posting_id = $4
        """, [str(rv_id), tailored.get("ats_score"), user_id, job_id])
        await db.commit()

    return {
        "success": True,
        "resume_version_id": str(rv_id),
        "ats_score": tailored.get("ats_score", 0),
        "claude_calls": claude_calls,
    }
