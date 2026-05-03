"""
Bridge skill — cross-chain asset transfers via Emblem Vault.

Handles bridging tokens between supported chains using Emblem
Vault's cross-chain infrastructure.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum

from skills.crypto.wallet import Chain


class BridgeStatus(Enum):
    INITIATED = "initiated"
    SOURCE_CONFIRMED = "source_confirmed"
    BRIDGING = "bridging"
    DESTINATION_PENDING = "destination_pending"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class BridgeRequest:
    """A cross-chain bridge transfer request."""
    from_chain: Chain
    to_chain: Chain
    token: str
    amount: float
    estimated_time_minutes: int = 5
    estimated_fee_usd: float = 0.0

    def describe(self) -> str:
        return (
            f"Bridge {self.amount} {self.token}: "
            f"{self.from_chain.value} → {self.to_chain.value} "
            f"(~{self.estimated_time_minutes}min, ~${self.estimated_fee_usd:.2f} fee)"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_chain": self.from_chain.value,
            "to_chain": self.to_chain.value,
            "token": self.token,
            "amount": self.amount,
            "estimated_time_minutes": self.estimated_time_minutes,
            "estimated_fee_usd": self.estimated_fee_usd,
        }


@dataclass
class BridgeResult:
    """Result of a bridge operation."""
    request: BridgeRequest
    status: BridgeStatus
    source_tx: Optional[str] = None
    destination_tx: Optional[str] = None
    actual_received: float = 0.0
    actual_fee: float = 0.0
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    @property
    def success(self) -> bool:
        return self.status == BridgeStatus.COMPLETED

    @property
    def duration_minutes(self) -> float:
        end = self.completed_at or time.time()
        return (end - self.started_at) / 60

    def describe(self) -> str:
        if self.success:
            return (
                f"Bridge complete: received {self.actual_received} {self.request.token} "
                f"on {self.request.to_chain.value} ({self.duration_minutes:.1f}min)"
            )
        return f"Bridge {self.status.value}: {self.request.describe()}"


class BridgeEngine:
    """Manages cross-chain bridge operations."""

    # Supported bridge routes.
    ROUTES: dict[tuple[str, str], list[str]] = {
        ("solana", "ethereum"): ["SOL", "USDC", "USDT"],
        ("ethereum", "solana"): ["ETH", "USDC", "USDT"],
        ("solana", "base"): ["SOL", "USDC"],
        ("base", "solana"): ["ETH", "USDC"],
        ("ethereum", "base"): ["ETH", "USDC", "USDT"],
        ("base", "ethereum"): ["ETH", "USDC", "USDT"],
        ("ethereum", "polygon"): ["ETH", "USDC", "USDT", "MATIC"],
        ("polygon", "ethereum"): ["ETH", "USDC", "USDT", "MATIC"],
        ("ethereum", "bsc"): ["ETH", "USDC", "USDT", "BNB"],
        ("bsc", "ethereum"): ["ETH", "USDC", "USDT", "BNB"],
    }

    def __init__(self) -> None:
        self._active_bridges: list[BridgeResult] = []
        self._history: list[BridgeResult] = []

    def is_route_supported(self, from_chain: Chain, to_chain: Chain, token: str) -> bool:
        """Check if a bridge route is available."""
        route = (from_chain.value, to_chain.value)
        supported = self.ROUTES.get(route, [])
        return token.upper() in [t.upper() for t in supported]

    def get_supported_tokens(self, from_chain: Chain, to_chain: Chain) -> list[str]:
        """Get tokens that can be bridged on this route."""
        route = (from_chain.value, to_chain.value)
        return self.ROUTES.get(route, [])

    async def estimate_bridge(
        self, from_chain: Chain, to_chain: Chain, token: str, amount: float
    ) -> BridgeRequest:
        """Estimate bridge time and fees."""
        # Fee estimates by route type.
        base_fee = 0.50  # Base fee in USD.
        time_estimate = 3  # Minutes.

        # Longer for certain chains.
        if from_chain == Chain.BITCOIN or to_chain == Chain.BITCOIN:
            time_estimate = 30
            base_fee = 5.0
        elif from_chain == Chain.ETHEREUM or to_chain == Chain.ETHEREUM:
            time_estimate = 10
            base_fee = 2.0

        return BridgeRequest(
            from_chain=from_chain,
            to_chain=to_chain,
            token=token,
            amount=amount,
            estimated_time_minutes=time_estimate,
            estimated_fee_usd=base_fee,
        )

    async def execute_bridge(self, request: BridgeRequest) -> BridgeResult:
        """Execute a bridge transfer via Emblem Vault."""
        result = BridgeResult(
            request=request,
            status=BridgeStatus.INITIATED,
        )
        self._active_bridges.append(result)
        # Actual execution would call Emblem Vault bridge API.
        return result

    def get_active_bridges(self) -> list[BridgeResult]:
        return [b for b in self._active_bridges if not b.success]

    def get_bridge_history(self, limit: int = 10) -> list[BridgeResult]:
        return self._history[-limit:]
