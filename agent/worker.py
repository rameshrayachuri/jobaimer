"""Temporal worker — registers workflows and activities."""
import asyncio
import logging
from temporalio.client import Client
from temporalio.worker import Worker
from app.core.config import settings

from agent.workflows.job_aimer import JobAimerWorkflow
from agent.workflows.scheduler import UserCycleScheduler
from agent.workflows.maintenance import StorageCleanupWorkflow, HardDeleteWorkflow

from agent.activities.discovery import discover_jobs
from agent.activities.scoring import quick_score_job
from agent.activities.tailoring import tailor_and_store_resume
from agent.activities.applying import apply_to_job
from agent.activities.status import update_application_status

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    logger.info(f"Connecting to Temporal at {settings.TEMPORAL_HOST}…")
    client = await Client.connect(settings.TEMPORAL_HOST, namespace=settings.TEMPORAL_NAMESPACE)

    logger.info("Starting Temporal worker…")
    async with Worker(
        client,
        task_queue=settings.TEMPORAL_TASK_QUEUE,
        workflows=[JobAimerWorkflow, UserCycleScheduler, StorageCleanupWorkflow, HardDeleteWorkflow],
        activities=[
            discover_jobs,
            quick_score_job,
            tailor_and_store_resume,
            apply_to_job,
            update_application_status,
        ],
    ):
        logger.info(f"Worker listening on queue: {settings.TEMPORAL_TASK_QUEUE}")
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
