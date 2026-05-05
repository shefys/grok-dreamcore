"""
Portfolio tracker — tracks holdings, P&L, allocation, and alerts.

Maintains a historical record of portfolio snapshots for
performance tracking over time. Generates alerts when
significant changes occur.
"""

from __future__ import annotations

import time
import json
from dataclasses import dataclass, field
from typing import Any, Optional

from skills.crypto.wallet import WalletSummary, TokenBalance, Chain


@dataclass
class PortfolioSnapshot:
    """Point-in-time capture of portfolio state."""
    total_usd: float
    chain_breakdown: dict[str, float]
    top_holdings: list[dict[str, Any]]
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_usd": self.total_usd,
            "chains": self.chain_breakdown,
            "top_holdings": self.top_holdings,
            "timestamp": self.timestamp,
        }


@dataclass
class PortfolioAlert:
    """An alert triggered by portfolio changes."""
    alert_type: str  # "price_change", "large_movement", "new_token", "rebalance_needed"
    message: str
    severity: str = "info"  # "info", "warning", "critical"
    token: Optional[str] = None
    chain: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.alert_type,
            "message": self.message,
            "severity": self.severity,
            "token": self.token,
            "timestamp": self.timestamp,
        }


class PortfolioTracker:
    """Tracks portfolio over time and generates alerts."""

    def __init__(
        self,
        alert_threshold_pct: float = 5.0,
        snapshot_interval_seconds: float = 14400,  # 4 hours.
    ) -> None:
        self._snapshots: list[PortfolioSnapshot] = []
        self._alerts: list[PortfolioAlert] = []
        self._alert_threshold = alert_threshold_pct
        self._snapshot_interval = snapshot_interval_seconds
        self._target_allocation: dict[str, float] = {}  # chain -> target percentage
        self._rebalance_threshold: float = 10.0  # Trigger rebalance alert at 10% drift.

    def record_snapshot(self, summary: WalletSummary) -> list[PortfolioAlert]:
        """Record a portfolio snapshot and check for alerts."""
        snapshot = PortfolioSnapshot(
            total_usd=summary.total_usd,
            chain_breakdown=summary.chain_breakdown,
            top_holdings=[b.to_dict() for b in summary.top_holdings()],
        )
        self._snapshots.append(snapshot)

        # Check for alerts.
        new_alerts = self._check_alerts(snapshot)
        self._alerts.extend(new_alerts)
        return new_alerts

    def get_performance(self, hours: float = 24) -> dict[str, Any]:
        """Get portfolio performance over a time period."""
        if len(self._snapshots) < 2:
            return {"error": "Not enough data yet."}

        cutoff = time.time() - (hours * 3600)
        past_snapshots = [s for s in self._snapshots if s.timestamp >= cutoff]
        if not past_snapshots:
            past_snapshots = [self._snapshots[0]]

        start = past_snapshots[0]
        end = self._snapshots[-1]

        change_usd = end.total_usd - start.total_usd
        change_pct = (change_usd / start.total_usd * 100) if start.total_usd > 0 else 0

        return {
            "start_value": start.total_usd,
            "end_value": end.total_usd,
            "change_usd": change_usd,
            "change_pct": round(change_pct, 2),
            "period_hours": hours,
            "snapshots": len(past_snapshots),
        }

    def set_target_allocation(self, allocation: dict[str, float]) -> None:
        """Set target portfolio allocation by chain (percentages, should sum to 100)."""
        total = sum(allocation.values())
        if abs(total - 100.0) > 1.0:
            raise ValueError(f"Allocation must sum to 100%, got {total}%")
        self._target_allocation = allocation

    def get_allocation_drift(self) -> dict[str, dict[str, float]]:
        """Compare current allocation to target."""
        if not self._snapshots or not self._target_allocation:
            return {}

        current = self._snapshots[-1]
        total = current.total_usd
        if total == 0:
            return {}

        drift: dict[str, dict[str, float]] = {}
        for chain, target_pct in self._target_allocation.items():
            actual_value = current.chain_breakdown.get(chain, 0)
            actual_pct = (actual_value / total * 100) if total > 0 else 0
            drift[chain] = {
                "target_pct": target_pct,
                "actual_pct": round(actual_pct, 1),
                "drift_pct": round(actual_pct - target_pct, 1),
                "actual_usd": actual_value,
            }
        return drift

    def get_recent_alerts(self, limit: int = 10) -> list[PortfolioAlert]:
        return self._alerts[-limit:]

    def format_daily_summary(self) -> str:
        """Generate a daily portfolio summary."""
        if not self._snapshots:
            return "No portfolio data yet."

        current = self._snapshots[-1]
        perf_24h = self.get_performance(hours=24)
        perf_7d = self.get_performance(hours=168)

        lines = [
            f"Portfolio: ${current.total_usd:,.2f}",
            f"24h: {perf_24h.get('change_pct', 0):+.2f}% (${perf_24h.get('change_usd', 0):+,.2f})",
            f"7d:  {perf_7d.get('change_pct', 0):+.2f}% (${perf_7d.get('change_usd', 0):+,.2f})",
            "",
            "Allocation:",
        ]
        for chain, value in sorted(
            current.chain_breakdown.items(), key=lambda x: x[1], reverse=True
        ):
            pct = (value / current.total_usd * 100) if current.total_usd > 0 else 0
            lines.append(f"  {chain}: ${value:,.2f} ({pct:.1f}%)")

        alerts = self.get_recent_alerts(3)
        if alerts:
            lines.append("")
            lines.append("Recent alerts:")
            for alert in alerts:
                lines.append(f"  [{alert.severity}] {alert.message}")

        return "\n".join(lines)

    # ---- Private ----

    def _check_alerts(self, snapshot: PortfolioSnapshot) -> list[PortfolioAlert]:
        """Check for alert conditions."""
        alerts: list[PortfolioAlert] = []

        if len(self._snapshots) < 2:
            return alerts

        prev = self._snapshots[-2]

        # Portfolio value change alert.
        if prev.total_usd > 0:
            change_pct = abs(
                (snapshot.total_usd - prev.total_usd) / prev.total_usd * 100
            )
            if change_pct >= self._alert_threshold:
                direction = "up" if snapshot.total_usd > prev.total_usd else "down"
                severity = "critical" if change_pct >= 10 else "warning"
                alerts.append(PortfolioAlert(
                    alert_type="price_change",
                    message=f"Portfolio {direction} {change_pct:.1f}% (${prev.total_usd:,.2f} → ${snapshot.total_usd:,.2f})",
                    severity=severity,
                ))

        # Allocation drift alert.
        if self._target_allocation:
            drift = self.get_allocation_drift()
            for chain, data in drift.items():
                if abs(data["drift_pct"]) >= self._rebalance_threshold:
                    alerts.append(PortfolioAlert(
                        alert_type="rebalance_needed",
                        message=f"{chain} allocation drifted {data['drift_pct']:+.1f}% from target ({data['target_pct']}% → {data['actual_pct']}%)",
                        severity="warning",
                        chain=chain,
                    ))

        return alerts
