"""
Scheduling skill — cron-style automations and scheduled tasks.

The agent can schedule recurring tasks like portfolio checks,
news digests, and custom automations that run unattended.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class ScheduledJob:
    """A recurring scheduled job."""
    name: str
    cron_expression: str
    description: str
    handler_name: str
    enabled: bool = True
    last_run: Optional[float] = None
    next_run: Optional[float] = None
    run_count: int = 0
    last_result: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    @property
    def id(self) -> str:
        import hashlib
        return hashlib.sha256(f"{self.name}:{self.created_at}".encode()).hexdigest()[:8]

    def record_run(self, result: str) -> None:
        self.last_run = time.time()
        self.run_count += 1
        self.last_result = result

    def format_status(self) -> str:
        status = "enabled" if self.enabled else "disabled"
        last = f"last: {time.strftime('%H:%M', time.localtime(self.last_run))}" if self.last_run else "never run"
        return f"[{status}] {self.name}: {self.cron_expression} ({last}, {self.run_count} runs)"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "cron": self.cron_expression,
            "description": self.description,
            "enabled": self.enabled,
            "run_count": self.run_count,
            "last_result": self.last_result,
        }


class Scheduler:
    """Manages scheduled automations."""

    # Default jobs for Adam's agent.
    DEFAULT_JOBS = [
        ScheduledJob(
            name="portfolio_check",
            cron_expression="0 */4 * * *",
            description="Check portfolio balances and record snapshot every 4 hours",
            handler_name="portfolio_snapshot",
        ),
        ScheduledJob(
            name="morning_briefing",
            cron_expression="0 8 * * *",
            description="Generate and send morning briefing at 8 AM",
            handler_name="daily_briefing",
        ),
        ScheduledJob(
            name="news_digest",
            cron_expression="0 12,18 * * *",
            description="Aggregate and summarize crypto news at noon and 6 PM",
            handler_name="news_digest",
        ),
        ScheduledJob(
            name="alert_check",
            cron_expression="*/15 * * * *",
            description="Check for portfolio alerts every 15 minutes",
            handler_name="alert_check",
        ),
        ScheduledJob(
            name="memory_nudge",
            cron_expression="*/30 * * * *",
            description="Check if anything should be memorized from recent activity",
            handler_name="memory_nudge",
        ),
    ]

    def __init__(self) -> None:
        self._jobs: dict[str, ScheduledJob] = {}
        self._handlers: dict[str, Callable] = {}

        # Register defaults.
        for job in self.DEFAULT_JOBS:
            self._jobs[job.id] = job

    def add_job(
        self,
        name: str,
        cron: str,
        description: str,
        handler_name: str,
    ) -> ScheduledJob:
        job = ScheduledJob(
            name=name,
            cron_expression=cron,
            description=description,
            handler_name=handler_name,
        )
        self._jobs[job.id] = job
        return job

    def remove_job(self, job_id: str) -> bool:
        return self._jobs.pop(job_id, None) is not None

    def enable_job(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job:
            job.enabled = True
            return True
        return False

    def disable_job(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job:
            job.enabled = False
            return True
        return False

    def get_jobs(self, enabled_only: bool = False) -> list[ScheduledJob]:
        jobs = list(self._jobs.values())
        if enabled_only:
            jobs = [j for j in jobs if j.enabled]
        return sorted(jobs, key=lambda j: j.name)

    def register_handler(self, name: str, handler: Callable) -> None:
        self._handlers[name] = handler

    async def run_job(self, job_id: str) -> str:
        """Manually trigger a job."""
        job = self._jobs.get(job_id)
        if not job:
            return f"Job {job_id} not found."

        handler = self._handlers.get(job.handler_name)
        if not handler:
            return f"No handler registered for {job.handler_name}."

        try:
            result = await handler()
            job.record_run(str(result)[:200])
            return str(result)
        except Exception as e:
            error = f"Job failed: {e}"
            job.record_run(error)
            return error

    def format_schedule(self) -> str:
        jobs = self.get_jobs()
        if not jobs:
            return "No scheduled jobs."
        lines = ["Scheduled jobs:"]
        for job in jobs:
            lines.append(f"  {job.format_status()}")
        return "\n".join(lines)

    def serialize(self) -> list[dict[str, Any]]:
        return [j.to_dict() for j in self._jobs.values()]
