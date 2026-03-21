"""Status update activity — persists application state changes."""
from temporalio import activity


@activity.defn
async def update_application_status(
    user_id: str,
    job_id: str,
    status: str,
    failure_reason: str | None,
    confirmation_id: str | None,
) -> bool:
    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        await db.execute("""
            UPDATE applications SET
                status = $1,
                failure_reason = $2,
                confirmation_id = $3,
                applied_at = CASE WHEN $1 = 'applied' THEN NOW() ELSE applied_at END,
                updated_at = NOW()
            WHERE user_id = $4 AND job_posting_id = $5
        """, [status, failure_reason, confirmation_id, user_id, job_id])
        await db.commit()
    return True
