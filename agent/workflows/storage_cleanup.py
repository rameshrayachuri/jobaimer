"""StorageCleanupWorkflow — deletes tailored resumes idle > 6 months.
Runs daily at 03:00 UTC via Temporal cron: '0 3 * * *'
"""
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy


@workflow.defn(name="StorageCleanupWorkflow")
class StorageCleanupWorkflow:

    @workflow.run
    async def run(self) -> dict:
        from agent.activities.storage import (
            find_resumes_eligible_for_deletion,
            filter_protected_resumes,
            delete_resume_batch,
        )

        eligible = await workflow.execute_activity(
            find_resumes_eligible_for_deletion,
            start_to_close_timeout=timedelta(minutes=5),
        )

        if not eligible:
            return {"deleted": 0, "message": "Nothing to clean up"}

        to_delete = await workflow.execute_activity(
            filter_protected_resumes,
            args=[eligible],
            start_to_close_timeout=timedelta(minutes=2),
        )

        # Process in batches of 100
        total_deleted = 0
        for i in range(0, len(to_delete), 100):
            batch = to_delete[i:i + 100]
            result = await workflow.execute_activity(
                delete_resume_batch,
                args=[batch],
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=RetryPolicy(maximum_attempts=3, backoff_coefficient=2.0),
            )
            total_deleted += result.get("deleted", 0)

        return {"deleted": total_deleted, "skipped": len(eligible) - len(to_delete)}
