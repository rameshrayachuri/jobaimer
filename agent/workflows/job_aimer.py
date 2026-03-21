"""
JobAimerWorkflow — one apply cycle for a single user.

Flow per cycle:
  1. Load user profile + plan limits
  2. Discover jobs across configured portals
  3. Quick-score each job (ATS match without full tailor)
  4. For jobs above threshold: tailor resume, apply, screenshot
  5. Persist results, update next_cycle_at
"""
from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from agent.activities.discovery import discover_jobs
    from agent.activities.scoring import quick_score_job
    from agent.activities.tailoring import tailor_and_store_resume
    from agent.activities.applying import apply_to_job
    from agent.activities.status import update_application_status

_RETRY = RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=5))
_LONG_RETRY = RetryPolicy(maximum_attempts=2, initial_interval=timedelta(seconds=30))


@dataclass
class CycleInput:
    user_id: str
    plan_id: str
    max_apps: int
    max_portals: int
    claude_passes: int
    min_ats_score: int = 70


@dataclass
class CycleResult:
    jobs_discovered: int
    jobs_applied: int
    jobs_failed: int
    jobs_skipped: int
    claude_calls: int


@workflow.defn
class JobAimerWorkflow:
    @workflow.run
    async def run(self, inp: CycleInput) -> CycleResult:
        ctx = workflow.info()
        workflow.logger.info(f"Cycle start — user={inp.user_id}")

        # ── 1. Discover jobs across portals ──────────────────────────────────
        raw_jobs = await workflow.execute_activity(
            discover_jobs,
            args=[inp.user_id, inp.max_portals],
            schedule_to_close_timeout=timedelta(minutes=10),
            retry_policy=_RETRY,
        )
        workflow.logger.info(f"Discovered {len(raw_jobs)} jobs")

        applied = 0
        failed = 0
        skipped = 0
        claude_calls = 0
        to_apply = []

        # ── 2. Quick-score all candidates (cheap, no full tailor) ─────────────
        for job in raw_jobs:
            if applied + len(to_apply) >= inp.max_apps:
                skipped += len(raw_jobs) - applied - failed - skipped - len(to_apply)
                break

            score = await workflow.execute_activity(
                quick_score_job,
                args=[inp.user_id, job["id"]],
                schedule_to_close_timeout=timedelta(minutes=2),
                retry_policy=_RETRY,
            )

            if score >= inp.min_ats_score:
                to_apply.append(job)
            else:
                skipped += 1
                workflow.logger.debug(f"Skipped {job['title']} @ {job['company']} (score={score})")

        # ── 3. Tailor + Apply ─────────────────────────────────────────────────
        for job in to_apply[:inp.max_apps]:
            try:
                # Tailor resume with multi-pass Claude refinement
                resume_result = await workflow.execute_activity(
                    tailor_and_store_resume,
                    args=[inp.user_id, job["id"], inp.claude_passes],
                    schedule_to_close_timeout=timedelta(minutes=8),
                    retry_policy=_LONG_RETRY,
                )
                claude_calls += resume_result.get("claude_calls", 1)

                if resume_result.get("ats_score", 0) < inp.min_ats_score:
                    skipped += 1
                    await workflow.execute_activity(
                        update_application_status,
                        args=[inp.user_id, job["id"], "skipped", "ATS score below threshold after tailoring", None],
                        schedule_to_close_timeout=timedelta(minutes=1),
                        retry_policy=_RETRY,
                    )
                    continue

                # Apply via Playwright
                apply_result = await workflow.execute_activity(
                    apply_to_job,
                    args=[inp.user_id, job["id"], resume_result["resume_version_id"]],
                    schedule_to_close_timeout=timedelta(minutes=5),
                    retry_policy=RetryPolicy(maximum_attempts=1),  # Don't re-apply
                )

                if apply_result.get("success"):
                    applied += 1
                    await workflow.execute_activity(
                        update_application_status,
                        args=[inp.user_id, job["id"], "applied",
                              None, apply_result.get("confirmation_id")],
                        schedule_to_close_timeout=timedelta(minutes=1),
                        retry_policy=_RETRY,
                    )
                else:
                    failed += 1
                    await workflow.execute_activity(
                        update_application_status,
                        args=[inp.user_id, job["id"], "failed",
                              apply_result.get("failure_reason", "Unknown"), None],
                        schedule_to_close_timeout=timedelta(minutes=1),
                        retry_policy=_RETRY,
                    )

            except Exception as e:
                workflow.logger.error(f"Job {job['id']} failed: {e}")
                failed += 1
                await workflow.execute_activity(
                    update_application_status,
                    args=[inp.user_id, job["id"], "failed", str(e)[:200], None],
                    schedule_to_close_timeout=timedelta(minutes=1),
                    retry_policy=_RETRY,
                )

        result = CycleResult(
            jobs_discovered=len(raw_jobs),
            jobs_applied=applied,
            jobs_failed=failed,
            jobs_skipped=skipped,
            claude_calls=claude_calls,
        )
        workflow.logger.info(f"Cycle complete — applied={applied} failed={failed} skipped={skipped}")
        return result
