"""Applications API — CRUD + soft-delete with S3 cleanup."""
from uuid import UUID
import boto3
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.core.config import settings
from app.core.database import get_db

router = APIRouter()
s3 = boto3.client("s3", region_name=settings.AWS_REGION)


class ApplicationStatusUpdate(BaseModel):
    status: str | None = None
    user_notes: str | None = None
    interview_at: str | None = None
    offer_received_at: str | None = None


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("/applications")
async def list_applications(
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * page_size
    query = """
        SELECT a.id, a.status, a.applied_at, a.ats_score, a.quick_score,
               a.failure_reason, a.manual_apply_url, a.user_notes,
               a.resume_version_id, a.screenshot_path, a.confirmation_id,
               jp.title, jp.company, jp.location, jp.portal,
               rv.s3_key IS NOT NULL as resume_available,
               rv.ats_score as resume_ats_score, rv.version_label
        FROM applications a
        LEFT JOIN job_postings jp ON jp.id = a.job_posting_id
        LEFT JOIN resume_versions rv ON rv.id = a.resume_version_id
        WHERE a.user_id = $1 AND a.deleted_at IS NULL
    """
    params: list = [str(current_user.id)]

    if status_filter:
        query += " AND a.status = $2"
        params.append(status_filter)

    query += " ORDER BY a.applied_at DESC NULLS LAST LIMIT $" + str(len(params) + 1)
    params.append(page_size)
    query += " OFFSET $" + str(len(params) + 1)
    params.append(offset)

    result = await db.execute(query, params)
    rows = result.fetchall()

    return {
        "applications": [
            {
                "id": str(r[0]), "status": r[1], "applied_at": r[2],
                "ats_score": r[3], "quick_score": r[4],
                "failure_reason": r[5], "manual_apply_url": r[6],
                "user_notes": r[7], "resume_version_id": str(r[8]) if r[8] else None,
                "confirmation_id": r[10],
                "job": {"title": r[11], "company": r[12], "location": r[13], "portal": r[14]},
                "resume": {"available": bool(r[15]), "ats_score": r[16], "version": r[17]},
            }
            for r in rows
        ],
        "page": page, "page_size": page_size,
    }


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/applications/stats")
async def application_stats(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute("""
        SELECT
            COUNT(*) FILTER (WHERE status = 'applied') as total_applied,
            COUNT(*) FILTER (WHERE status = 'interview_scheduled') as interviews,
            COUNT(*) FILTER (WHERE status = 'offer_received') as offers,
            COUNT(*) FILTER (WHERE status = 'accepted') as accepted,
            AVG(ats_score) FILTER (WHERE ats_score IS NOT NULL) as avg_ats,
            COUNT(*) FILTER (WHERE applied_at >= NOW() - INTERVAL '7 days') as this_week
        FROM applications
        WHERE user_id = $1 AND deleted_at IS NULL
    """, [str(current_user.id)])
    row = result.fetchone()
    return {
        "total_applied": row[0] or 0, "interviews": row[1] or 0,
        "offers": row[2] or 0, "accepted": row[3] or 0,
        "avg_ats_score": round(float(row[4]), 1) if row[4] else 0.0,
        "this_week": row[5] or 0,
    }


# ── Single application ────────────────────────────────────────────────────────

@router.get("/applications/{application_id}")
async def get_application(
    application_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute("""
        SELECT a.*, jp.title, jp.company, jp.location, jp.portal, jp.apply_url,
               rv.s3_key, rv.version_label, rv.ats_score as rv_ats
        FROM applications a
        LEFT JOIN job_postings jp ON jp.id = a.job_posting_id
        LEFT JOIN resume_versions rv ON rv.id = a.resume_version_id
        WHERE a.id = $1 AND a.user_id = $2 AND a.deleted_at IS NULL
    """, [str(application_id), str(current_user.id)])
    row = result.fetchone()
    if not row:
        raise HTTPException(404, "Application not found")
    return dict(zip([d[0] for d in result.cursor.description], row))


# ── Patch status ──────────────────────────────────────────────────────────────

@router.patch("/applications/{application_id}")
async def update_application(
    application_id: UUID,
    body: ApplicationStatusUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify ownership
    result = await db.execute(
        "SELECT id FROM applications WHERE id = $1 AND user_id = $2 AND deleted_at IS NULL",
        [str(application_id), str(current_user.id)]
    )
    if not result.fetchone():
        raise HTTPException(404, "Application not found")

    updates = {}
    if body.status: updates["status"] = body.status
    if body.user_notes is not None: updates["user_notes"] = body.user_notes
    if body.interview_at: updates["interview_at"] = body.interview_at
    if body.offer_received_at: updates["offer_received_at"] = body.offer_received_at

    if not updates:
        raise HTTPException(400, "No fields to update")

    set_clause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(updates.keys()))
    values = [str(application_id)] + list(updates.values())
    await db.execute(
        f"UPDATE applications SET {set_clause}, updated_at = NOW() WHERE id = $1", values
    )
    return {"updated": True, "fields": list(updates.keys())}


# ── Delete application ────────────────────────────────────────────────────────

@router.delete("/applications/{application_id}")
async def delete_application(
    application_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete application. Deletes S3 screenshot + tailored resume from S3 immediately."""
    result = await db.execute("""
        SELECT a.status, a.screenshot_path, a.resume_version_id,
               rv.s3_key, rv.file_size_bytes
        FROM applications a
        LEFT JOIN resume_versions rv ON rv.id = a.resume_version_id
        WHERE a.id = $1 AND a.user_id = $2 AND a.deleted_at IS NULL
    """, [str(application_id), str(current_user.id)])
    row = result.fetchone()
    if not row:
        raise HTTPException(404, "Application not found")

    app_status, screenshot_path, resume_version_id, s3_key, file_size = row

    # Block if currently being processed
    if app_status in ("tailoring_resume", "applying"):
        raise HTTPException(409, detail={
            "error": "in_progress",
            "message": "Application is being filed. Try again in a few minutes.",
        })

    # Delete screenshot from S3
    if screenshot_path:
        try:
            s3.delete_object(Bucket=settings.S3_RESUME_BUCKET, Key=screenshot_path)
        except Exception:
            pass  # Already gone — idempotent

    # Soft-delete application
    await db.execute("""
        UPDATE applications SET deleted_at = NOW(), deleted_by = 'user' WHERE id = $1
    """, [str(application_id)])

    resume_deleted = False
    bytes_freed = 0

    # Delete resume if no other active application references it
    if resume_version_id and s3_key:
        other_apps = await db.execute("""
            SELECT COUNT(*) FROM applications
            WHERE resume_version_id = $1 AND id != $2 AND deleted_at IS NULL
        """, [str(resume_version_id), str(application_id)])
        count = other_apps.fetchone()[0]

        if count == 0:
            try:
                s3.delete_object(Bucket=settings.S3_RESUME_BUCKET, Key=s3_key)
                bytes_freed = file_size or 0
            except Exception:
                pass

            await db.execute("""
                UPDATE resume_versions
                SET deleted_at = NOW(), deletion_reason = 'user_deleted', s3_key = NULL
                WHERE id = $1
            """, [str(resume_version_id)])
            resume_deleted = True

            # Log to storage_cleanup_log
            await db.execute("""
                INSERT INTO storage_cleanup_log (resume_version_id, user_id, s3_key, reason, bytes_freed)
                VALUES ($1, $2, $3, 'user_deleted', $4)
            """, [str(resume_version_id), str(current_user.id), s3_key, bytes_freed])

    # Log deletion
    await db.execute("""
        INSERT INTO user_deletion_log (user_id, resource_type, resource_id, bytes_freed)
        VALUES ($1, 'application', $2, $3)
    """, [str(current_user.id), str(application_id), bytes_freed])

    return {"deleted": True, "resume_also_deleted": resume_deleted, "bytes_freed": bytes_freed}


# ── Delete resume only ────────────────────────────────────────────────────────

@router.delete("/applications/{application_id}/resume")
async def delete_application_resume(
    application_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete only the tailored resume file; keep application record."""
    result = await db.execute("""
        SELECT rv.id, rv.s3_key, rv.file_size_bytes, rv.deleted_at
        FROM applications a
        LEFT JOIN resume_versions rv ON rv.id = a.resume_version_id
        WHERE a.id = $1 AND a.user_id = $2 AND a.deleted_at IS NULL
    """, [str(application_id), str(current_user.id)])
    row = result.fetchone()
    if not row:
        raise HTTPException(404, "Application not found")

    rv_id, s3_key, file_size, deleted_at = row

    if deleted_at:
        return {"deleted": True, "already_deleted": True}

    if s3_key:
        try:
            s3.delete_object(Bucket=settings.S3_RESUME_BUCKET, Key=s3_key)
        except Exception:
            pass

    await db.execute("""
        UPDATE resume_versions
        SET deleted_at = NOW(), deletion_reason = 'user_deleted', s3_key = NULL
        WHERE id = $1
    """, [str(rv_id)])

    await db.execute("""
        INSERT INTO storage_cleanup_log (resume_version_id, user_id, s3_key, reason, bytes_freed)
        VALUES ($1, $2, $3, 'user_deleted', $4)
    """, [str(rv_id), str(current_user.id), s3_key, file_size or 0])

    return {"deleted": True, "resume_version_id": str(rv_id), "bytes_freed": file_size or 0}


# ── Resume download (pre-signed S3 URL) ──────────────────────────────────────

@router.get("/applications/{application_id}/resume")
async def download_resume(
    application_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns a 15-minute pre-signed S3 URL for the tailored resume PDF."""
    result = await db.execute("""
        SELECT rv.s3_key, rv.file_name, rv.deleted_at
        FROM applications a
        JOIN resume_versions rv ON rv.id = a.resume_version_id
        WHERE a.id = $1 AND a.user_id = $2 AND a.deleted_at IS NULL
    """, [str(application_id), str(current_user.id)])
    row = result.fetchone()
    if not row:
        raise HTTPException(404, "Application not found")

    s3_key, file_name, deleted_at = row
    if deleted_at or not s3_key:
        raise HTTPException(404, "Resume has been deleted")

    url = s3.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.S3_RESUME_BUCKET,
            "Key": s3_key,
            "ResponseContentDisposition": f'attachment; filename="{file_name}"',
            "ResponseContentType": "application/pdf",
        },
        ExpiresIn=900,  # 15 minutes
    )

    # Log download
    await db.execute("""
        INSERT INTO resume_download_log (user_id, resume_version_id, application_id)
        VALUES ($1, (SELECT resume_version_id FROM applications WHERE id = $2), $2)
    """, [str(current_user.id), str(application_id)])

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=url, status_code=302)


@router.get("/applications/{application_id}/resume/status")
async def resume_status(
    application_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute("""
        SELECT rv.deleted_at, rv.deletion_reason, rv.s3_key IS NOT NULL as has_file
        FROM applications a
        LEFT JOIN resume_versions rv ON rv.id = a.resume_version_id
        WHERE a.id = $1 AND a.user_id = $2 AND a.deleted_at IS NULL
    """, [str(application_id), str(current_user.id)])
    row = result.fetchone()
    if not row:
        raise HTTPException(404, "Application not found")
    return {
        "available": bool(row[2]) and row[0] is None,
        "deleted_at": row[0],
        "deletion_reason": row[1],
    }
