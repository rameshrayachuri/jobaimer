"""Maintenance workflows — storage cleanup and hard delete."""
from datetime import timedelta
from temporalio import workflow


@workflow.defn
class StorageCleanupWorkflow:
    """Runs daily at 03:00 UTC. Deletes tailored resumes older than 6 months."""

    @workflow.run
    async def run(self) -> dict:
        workflow.logger.info("StorageCleanupWorkflow starting")

        result = await workflow.execute_activity(
            "cleanup_old_resumes",
            schedule_to_close_timeout=timedelta(hours=1),
        )

        workflow.logger.info(f"Cleanup done: {result}")
        return result


@workflow.defn
class HardDeleteWorkflow:
    """Runs daily at 04:00 UTC. Hard-deletes soft-deleted applications after 30 days."""

    @workflow.run
    async def run(self) -> dict:
        workflow.logger.info("HardDeleteWorkflow starting")

        result = await workflow.execute_activity(
            "hard_delete_expired_applications",
            schedule_to_close_timeout=timedelta(hours=1),
        )

        workflow.logger.info(f"Hard delete done: {result}")
        return result
