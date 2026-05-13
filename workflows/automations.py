"""
Workflows — automated multi-step operations.

Workflows chain multiple skills together into higher-level
automations. For example, the morning briefing workflow calls
portfolio tracker, task manager, news research, and formats
everything into a single summary.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional, Callable, Awaitable

from skills.portfolio.tracker import PortfolioTracker
from skills.assistant.tasks import TaskManager
from skills.research.market import ResearchEngine
from skills.scheduling.scheduler import Scheduler


@dataclass
class WorkflowResult:
    """Result of a workflow execution."""
    name: str
    output: str
    steps_completed: int
    total_steps: int
    duration_seconds: float
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.steps_completed == self.total_steps and not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "output": self.output[:500],
            "steps_completed": self.steps_completed,
            "total_steps": self.total_steps,
            "duration": round(self.duration_seconds, 2),
            "success": self.success,
            "errors": self.errors,
        }


class WorkflowEngine:
    """Executes multi-step automated workflows."""

    def __init__(
        self,
        portfolio: PortfolioTracker,
        tasks: TaskManager,
        research: ResearchEngine,
    ) -> None:
        self._portfolio = portfolio
        self._tasks = tasks
        self._research = research

    async def morning_briefing(self) -> WorkflowResult:
        """Generate a comprehensive morning briefing.

        Steps:
        1. Get portfolio summary and 24h performance.
        2. Check for overdue tasks and urgent items.
        3. Get market overview.
        4. Get recent news.
        5. Compile into a single briefing.
        """
        start = time.time()
        parts: list[str] = []
        steps = 0
        total = 5
        errors: list[str] = []

        # Step 1: Portfolio.
        try:
            portfolio_summary = self._portfolio.format_daily_summary()
            parts.append(portfolio_summary)
            steps += 1
        except Exception as e:
            errors.append(f"Portfolio: {e}")

        # Step 2: Tasks.
        try:
            task_briefing = self._tasks.format_daily_briefing()
            parts.append(task_briefing)
            steps += 1
        except Exception as e:
            errors.append(f"Tasks: {e}")

        # Step 3: Market overview.
        try:
            market = await self._research.get_market_overview()
            parts.append(market.format_summary())
            steps += 1
        except Exception as e:
            errors.append(f"Market: {e}")

        # Step 4: News.
        try:
            news = await self._research.get_news(limit=3)
            if news:
                parts.append("Recent news:")
                for item in news:
                    parts.append(f"  - {item.format_brief()}")
            else:
                parts.append("No recent news.")
            steps += 1
        except Exception as e:
            errors.append(f"News: {e}")

        # Step 5: Compile.
        steps += 1
        output = "\n\n".join(parts)

        return WorkflowResult(
            name="morning_briefing",
            output=output,
            steps_completed=steps,
            total_steps=total,
            duration_seconds=time.time() - start,
            errors=errors,
        )

    async def portfolio_snapshot(self) -> WorkflowResult:
        """Take a portfolio snapshot and check alerts."""
        start = time.time()
        parts: list[str] = []
        steps = 0
        errors: list[str] = []

        try:
            summary = self._portfolio.format_daily_summary()
            parts.append(summary)
            steps += 1
        except Exception as e:
            errors.append(str(e))

        alerts = self._portfolio.get_recent_alerts(5)
        if alerts:
            parts.append("Alerts:")
            for alert in alerts:
                parts.append(f"  [{alert.severity}] {alert.message}")
        steps += 1

        return WorkflowResult(
            name="portfolio_snapshot",
            output="\n".join(parts),
            steps_completed=steps,
            total_steps=2,
            duration_seconds=time.time() - start,
            errors=errors,
        )

    async def token_deep_dive(self, symbol: str) -> WorkflowResult:
        """Research a token in depth.

        Steps:
        1. Look up token info and price.
        2. Check safety score.
        3. Get related news.
        4. Check if we hold it.
        5. Compile analysis.
        """
        start = time.time()
        parts: list[str] = []
        steps = 0
        total = 4
        errors: list[str] = []

        # Step 1: Token info.
        try:
            token = await self._research.lookup_token(symbol)
            if token:
                parts.append(token.format_summary())
            else:
                parts.append(f"Could not find token: {symbol}")
            steps += 1
        except Exception as e:
            errors.append(f"Lookup: {e}")

        # Step 2: News.
        try:
            news = await self._research.get_news(limit=3, token=symbol)
            if news:
                parts.append(f"\nRecent {symbol} news:")
                for item in news:
                    parts.append(f"  - {item.format_brief()}")
            steps += 1
        except Exception as e:
            errors.append(f"News: {e}")

        # Step 3: Market context.
        try:
            market = await self._research.get_market_overview()
            parts.append(f"\nBTC: ${market.btc_price:,.0f} | Fear/Greed: {market.fear_greed_index}")
            steps += 1
        except Exception as e:
            errors.append(f"Market: {e}")

        steps += 1  # Compile step.

        return WorkflowResult(
            name="token_deep_dive",
            output="\n".join(parts),
            steps_completed=steps,
            total_steps=total,
            duration_seconds=time.time() - start,
            errors=errors,
        )

    async def news_digest(self) -> WorkflowResult:
        """Aggregate and summarize recent crypto news."""
        start = time.time()
        try:
            news = await self._research.get_news(limit=10)
            if not news:
                return WorkflowResult(
                    name="news_digest",
                    output="No news to report.",
                    steps_completed=1,
                    total_steps=1,
                    duration_seconds=time.time() - start,
                )

            lines = ["News digest:"]
            for item in news:
                lines.append(f"  [{item.source}] {item.title}")
                if item.summary:
                    lines.append(f"    {item.summary[:100]}")

            return WorkflowResult(
                name="news_digest",
                output="\n".join(lines),
                steps_completed=1,
                total_steps=1,
                duration_seconds=time.time() - start,
            )
        except Exception as e:
            return WorkflowResult(
                name="news_digest",
                output="",
                steps_completed=0,
                total_steps=1,
                duration_seconds=time.time() - start,
                errors=[str(e)],
            )
