"""Storage activities — resume lifecycle management."""
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import boto3
from temporalio import activity

logger = logging.getLogger(__name__)
S3_BUCKET = os.environ.get("S3_RESUME_BUCKET", "jobaimer-resumes-dev")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

_s3 = None


def get_s3():
    global _s3
    if _s3 is None:
        _s3 = boto3.client("s3", region_name=AWS_REGION)
    return _s3


@activity.defn
async def find_resumes_eligible_for_deletion() -> list[dict[str, Any]]:
    """Find tailored resumes not accessed in 6+ months."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=180)
    from agent.db import get_db_pool
    pool = await get_db_pool()
    rows = await pool.fetch("""
        SELECT id, s3_key, user_id, file_size_bytes, last_accessed_at
        FROM resume_versions
        WHERE version_type = 'tailored'
          AND deleted_at IS NULL
          AND s3_key IS NOT NULL
          AND last_accessed_at < $1
        ORDER BY last_accessed_at ASC
        LIMIT 10000
    """, cutoff)
    return [dict(r) for r in rows]


@activity.defn
async def filter_protected_resumes(candidates: list[dict]) -> list[dict]:
    """Remove resumes tied to active/interview/offer applications."""
    if not candidates:
        return []
    ids = [str(c["id"]) for c in candidates]
    from agent.db import get_db_pool
    pool = await get_db_pool()
    protected = await pool.fetch("""
        SELECT DISTINCT resume_version_id::text
        FROM applications
        WHERE resume_version_id = ANY($1::uuid[])
          AND status IN ('interview_scheduled','offer_received','accepted')
          AND deleted_at IS NULL
    """, ids)
    protected_ids = {r["resume_version_id"] for r in protected}
    return [c for c in candidates if str(c["id"]) not in protected_ids]


@activity.defn
async def delete_resume_batch(batch: list[dict]) -> dict:
    """Soft-delete DB records + delete S3 objects for a batch."""
    deleted = 0
    failed = 0
    from agent.db import get_db_pool
    pool = await get_db_pool()

    for item in batch:
        try:
            # 1. Soft-delete DB record first
            await pool.execute("""
                UPDATE resume_versions
                SET deleted_at = NOW(), deletion_reason = 'auto_6month_inactivity', s3_key = NULL
                WHERE id = $1
            """, item["id"])

            # 2. Delete from S3
            if item.get("s3_key"):
                try:
                    get_s3().delete_object(Bucket=S3_BUCKET, Key=item["s3_key"])
                except Exception:
                    pass  # Idempotent

            # 3. Log
            await pool.execute("""
                INSERT INTO storage_cleanup_log
                    (resume_version_id, user_id, s3_key, reason, bytes_freed)
                VALUES ($1,$2,$3,'auto_6month_inactivity',$4)
            """, item["id"], item["user_id"], item.get("s3_key"), item.get("file_size_bytes", 0))
            deleted += 1
        except Exception as e:
            logger.error(f"Failed to delete resume {item.get('id')}: {e}")
            failed += 1

    return {"deleted": deleted, "failed": failed}


@activity.defn
async def hard_delete_old_applications() -> int:
    """Permanently remove application rows soft-deleted > 30 days ago."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    from agent.db import get_db_pool
    pool = await get_db_pool()
    result = await pool.execute("""
        DELETE FROM applications WHERE deleted_at IS NOT NULL AND deleted_at < $1
    """, cutoff)
    count = int(result.split()[-1]) if result else 0
    logger.info(f"Hard-deleted {count} applications")
    return count


@activity.defn
async def hard_delete_old_resumes() -> int:
    """Permanently remove resume_version rows soft-deleted > 30 days, S3 already gone."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    from agent.db import get_db_pool
    pool = await get_db_pool()
    result = await pool.execute("""
        DELETE FROM resume_versions
        WHERE deleted_at IS NOT NULL AND deleted_at < $1 AND s3_key IS NULL
    """, cutoff)
    count = int(result.split()[-1]) if result else 0
    logger.info(f"Hard-deleted {count} resume_versions")
    return count
