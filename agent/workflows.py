"""JobAimer Temporal Workflows — durable orchestration of the job application agent."""
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from agent.activities import (
        discover_jobs, score_ats_match, tailor_resume,
        submit_application, cleanup_expired_resumes,
        cleanup_deleted_resume_s3, hard_delete_user_data,
        notify_application_status,
    )
    from agent.config import settings

RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=30),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=10),
    maximum_attempts=3,
)

LONG_RETRY = RetryPolicy(
    initial_interval=timedelta(minutes=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(hours=1),
    maximum_attempts=5,
)


# ---------------------------------------------------------------------------
# Main job application workflow — runs per-user every 4 hours
# ---------------------------------------------------------------------------

@workflow.defn
class JobAimerWorkflow:
    """Core workflow: discover → score → tailor → apply for a single user cycle."""

    @workflow.run
    async def run(self, user_id: str, plan_id: str) -> dict:
        results = {"applied": 0, "skipped": 0, "errors": 0, "tailored": 0}
        limits = settings.PLAN_LIMITS.get(plan_id, settings.PLAN_LIMITS["free_trial"])

        workflow.logger.info(f"Starting job cycle for user={user_id} plan={plan_id}")

        # Step 1: Discover jobs
        jobs = await workflow.execute_activity(
            discover_jobs,
            args=[user_id, plan_id],
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RETRY_POLICY,
        )
        workflow.logger.info(f"Discovered {len(jobs)} jobs for user={user_id}")

        applied_this_cycle = 0
        max_per_cycle = min(limits["max_apps"], settings.MAX_APPLY_PER_CYCLE)

        for job in jobs:
            if applied_this_cycle >= max_per_cycle:
                break

            # Step 2: Score ATS match
            score_result = await workflow.execute_activity(
                score_ats_match,
                args=[user_id, job],
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RETRY_POLICY,
            )

            score = float(score_result.get("score", 0))
            if score < settings.ATS_MATCH_THRESHOLD:
                workflow.logger.info(f"Skipping {job.get('title')} — ATS score {score:.2f} below threshold")
                results["skipped"] += 1
                continue

            # Step 3: Tailor resume (if plan allows)
            tailored_id = None
            tailor_passes = limits.get("tailor_passes", 0)
            if tailor_passes > 0:
                try:
                    tailored_id = await workflow.execute_activity(
                        tailor_resume,
                        args=[user_id, job, tailor_passes],
                        start_to_close_timeout=timedelta(minutes=5),
                        retry_policy=RETRY_POLICY,
                    )
                    results["tailored"] += 1
                except Exception as e:
                    workflow.logger.error(f"Tailor failed for {job.get('title')}: {e}")

            # Step 4: Submit application
            sub_result = await workflow.execute_activity(
                submit_application,
                args=[user_id, job, tailored_id],
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RETRY_POLICY,
            )

            if sub_result.get("success"):
                results["applied"] += 1
                applied_this_cycle += 1
                workflow.logger.info(f"Applied to {job.get('title')} at {job.get('company')}")
            else:
                results["errors"] += 1

        workflow.logger.info(f"Cycle complete for user={user_id}: {results}")
        return results


# ---------------------------------------------------------------------------
# User Cycle Scheduler — orchestrates per-user workflows on a cron schedule
# ---------------------------------------------------------------------------

@workflow.defn
class UserCycleScheduler:
    """Spawns JobAimerWorkflow for all active users on a 4-hour cron."""

    @workflow.run
    async def run(self) -> None:
        import asyncpg
        conn = await asyncpg.connect(settings.SUPABASE_DB_URL)
        try:
            users = await conn.fetch("""
                SELECT ap.user_id, s.plan_id
                FROM applicant_profiles ap
                JOIN subscriptions s ON s.user_id = ap.user_id
                WHERE ap.agent_status = 'active'
                  AND s.status IN ('active', 'trialing')
                  AND (ap.next_cycle_at IS NULL OR ap.next_cycle_at <= NOW())
            """)
            workflow.logger.info(f"Starting cycles for {len(users)} active users")
            for user in users:
                await workflow.execute_child_workflow(
                    JobAimerWorkflow,
                    args=[str(user["user_id"]), user["plan_id"]],
                    id=f"jobaimer-{user['user_id']}-{workflow.now().strftime('%Y%m%d%H')}",
                )
                await conn.execute("""
                    UPDATE applicant_profiles
                    SET last_cycle_at = NOW(),
                        next_cycle_at = NOW() + INTERVAL '4 hours'
                    WHERE user_id = $1
                """, user["user_id"])
        finally:
            await conn.close()


# ---------------------------------------------------------------------------
# Storage Cleanup Workflow — daily cron to delete expired resumes
# ---------------------------------------------------------------------------

@workflow.defn
class StorageCleanupWorkflow:
    """Daily cleanup of S3 resume objects past their 6-month TTL."""

    @workflow.run
    async def run(self) -> dict:
        result = await workflow.execute_activity(
            cleanup_expired_resumes,
            start_to_close_timeout=timedelta(minutes=30),
            retry_policy=LONG_RETRY,
        )
        workflow.logger.info(f"Storage cleanup: {result}")
        return result


# ---------------------------------------------------------------------------
# Hard Delete Workflow — fires after 30-day grace period on account deletion
# ---------------------------------------------------------------------------

@workflow.defn
class HardDeleteWorkflow:
    """Waits 30 days then permanently purges all user data from DB + S3."""

    @workflow.run
    async def run(self, user_id: str, grace_days: int = 30) -> dict:
        workflow.logger.info(f"HardDelete scheduled for user={user_id} in {grace_days} days")

        # Wait for grace period
        await workflow.execute_local_activity(
            lambda: None,  # no-op; real sleep via timer
            start_to_close_timeout=timedelta(seconds=1),
        )
        # Temporal timer — survives worker restarts
        await workflow.sleep(timedelta(days=grace_days))

        import asyncpg
        conn = await asyncpg.connect(settings.SUPABASE_DB_URL)
        try:
            deletion = await conn.fetchrow("""
                SELECT user_id FROM user_deletion_log
                WHERE user_id = $1 AND restored_at IS NULL
                ORDER BY created_at DESC LIMIT 1
            """, user_id)
            if not deletion:
                workflow.logger.info(f"User {user_id} restored during grace period — aborting hard delete")
                return {"status": "cancelled", "reason": "user_restored"}
        finally:
            await conn.close()

        result = await workflow.execute_activity(
            hard_delete_user_data,
            args=[user_id],
            start_to_close_timeout=timedelta(minutes=15),
            retry_policy=LONG_RETRY,
        )
        workflow.logger.info(f"Hard delete complete for user={user_id}: {result}")
        return {"status": "completed", **result}


# ---------------------------------------------------------------------------
# Resume S3 Deletion Workflow — fires when user deletes a resume
# ---------------------------------------------------------------------------

@workflow.defn
class ResumeS3DeleteWorkflow:
    """Async S3 object deletion with retry, triggered by user action."""

    @workflow.run
    async def run(self, s3_key: str, resume_id: str) -> bool:
        return await workflow.execute_activity(
            cleanup_deleted_resume_s3,
            args=[s3_key, resume_id],
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=LONG_RETRY,
        )


# ---------------------------------------------------------------------------
# Coupon Expiry Check — daily cron
# ---------------------------------------------------------------------------

@workflow.defn
class CouponExpiryCheckWorkflow:
    """Deactivates coupons past their valid_until date."""

    @workflow.run
    async def run(self) -> dict:
        import asyncpg
        conn = await asyncpg.connect(settings.SUPABASE_DB_URL)
        try:
            result = await conn.execute("""
                UPDATE coupons SET is_active=false, updated_at=NOW()
                WHERE valid_until < NOW() AND is_active=true
            """)
            count = int(result.split()[-1])
            return {"deactivated": count}
        finally:
            await conn.close()
