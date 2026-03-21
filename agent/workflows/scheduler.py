"""UserCycleScheduler — durable cron that triggers per-user apply cycles."""
import asyncio
from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from agent.workflows.job_aimer import JobAimerWorkflow, CycleInput
    from app.core.config import settings


@workflow.defn
class UserCycleScheduler:
    """Long-running workflow per user. Wakes every APPLY_CYCLE_HOURS hours."""

    @workflow.run
    async def run(self, user_id: str) -> None:
        workflow.logger.info(f"Scheduler started for user={user_id}")

        while True:
            # Load latest user config from DB
            profile = await workflow.execute_activity(
                "load_user_cycle_config",
                args=[user_id],
                schedule_to_close_timeout=timedelta(minutes=1),
            )

            if not profile or profile.get("agent_status") != "active":
                workflow.logger.info(f"User {user_id} paused/stopped — scheduler sleeping")
                await workflow.sleep(timedelta(hours=1))
                continue

            # Run one apply cycle as child workflow
            cycle_input = CycleInput(
                user_id=user_id,
                plan_id=profile["plan_id"],
                max_apps=profile["max_apps_per_cycle"],
                max_portals=profile["max_portals"],
                claude_passes=profile["claude_tailor_passes"],
                min_ats_score=int(settings.MIN_ATS_SCORE if hasattr(settings, 'MIN_ATS_SCORE') else 70),
            )

            cycle_handle = await workflow.start_child_workflow(
                JobAimerWorkflow.run,
                args=[cycle_input],
                id=f"cycle-{user_id}-{workflow.now().isoformat()}",
                retry_policy=RetryPolicy(maximum_attempts=1),
            )

            try:
                result = await asyncio.wait_for(
                    cycle_handle,
                    timeout=timedelta(hours=3).total_seconds(),
                )
                workflow.logger.info(f"Cycle complete for {user_id}: {result}")
            except Exception as e:
                workflow.logger.error(f"Cycle failed for {user_id}: {e}")

            # Update next_cycle_at in DB
            await workflow.execute_activity(
                "update_next_cycle_at",
                args=[user_id, settings.APPLY_CYCLE_HOURS],
                schedule_to_close_timeout=timedelta(minutes=1),
            )

            # Sleep until next cycle
            await workflow.sleep(timedelta(hours=settings.APPLY_CYCLE_HOURS))
