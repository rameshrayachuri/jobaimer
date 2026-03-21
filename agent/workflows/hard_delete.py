"""HardDeleteWorkflow — permanently removes soft-deleted rows after 30 days.
Runs daily at 04:00 UTC: '0 4 * * *'
"""
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy


@workflow.defn(name="HardDeleteWorkflow")
class HardDeleteWorkflow:

    @workflow.run
    async def run(self) -> dict:
        from agent.activities.storage import hard_delete_old_applications, hard_delete_old_resumes

        apps = await workflow.execute_activity(
            hard_delete_old_applications,
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        resumes = await workflow.execute_activity(
            hard_delete_old_resumes,
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        return {"hard_deleted_applications": apps, "hard_deleted_resumes": resumes}
