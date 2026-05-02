"""
Trading skill — swap execution, limit orders, and trade management.

All trades go through Emblem Vault's trading infrastructure.
Transactions below the auto-approve threshold execute immediately.
Transactions above the confirmation threshold require explicit approval.
"""

from __future__ import annotations

import time
import hashlib
from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum

from skills.crypto.wallet import Chain


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


class OrderStatus(Enum):
    PENDING_APPROVAL = "pending_approval"
    SUBMITTED = "submitted"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    FAILED = "failed"
    EXPIRED = "expired"


class TradeDirection(Enum):
    BUY = "buy"
    SELL = "sell"
    SWAP = "swap"


@dataclass
class TradeRequest:
    """A request to execute a trade."""
    direction: TradeDirection
    from_token: str
    to_token: str
    amount: float
    chain: Chain
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = None
    slippage_bps: int = 100  # 1% default.
    expires_at: Optional[float] = None

    @property
    def id(self) -> str:
        raw = f"{self.direction.value}:{self.from_token}:{self.to_token}:{self.amount}:{time.time()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:12]

    @property
    def is_limit(self) -> bool:
        return self.order_type in (OrderType.LIMIT, OrderType.STOP_LOSS, OrderType.TAKE_PROFIT)

    def describe(self) -> str:
        if self.direction == TradeDirection.SWAP:
            return f"Swap {self.amount} {self.from_token} → {self.to_token} on {self.chain.value}"
        return f"{self.direction.value.title()} {self.amount} {self.to_token} on {self.chain.value}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "direction": self.direction.value,
            "from_token": self.from_token,
            "to_token": self.to_token,
            "amount": self.amount,
            "chain": self.chain.value,
            "order_type": self.order_type.value,
            "limit_price": self.limit_price,
            "slippage_bps": self.slippage_bps,
        }


@dataclass
class TradeResult:
    """Result of a trade execution."""
    request_id: str
    status: OrderStatus
    tx_hash: Optional[str] = None
    filled_amount: float = 0.0
    filled_price: float = 0.0
    fee_amount: float = 0.0
    fee_token: str = ""
    executed_at: float = field(default_factory=time.time)
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.status in (OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED)

    def describe(self) -> str:
        if self.success:
            return (
                f"Filled: {self.filled_amount} @ ${self.filled_price:.6f} "
                f"(fee: {self.fee_amount} {self.fee_token}) "
                f"TX: {self.tx_hash or 'pending'}"
            )
        if self.error:
            return f"Failed: {self.error}"
        return f"Status: {self.status.value}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "status": self.status.value,
            "tx_hash": self.tx_hash,
            "filled_amount": self.filled_amount,
            "filled_price": self.filled_price,
            "fee_amount": self.fee_amount,
            "success": self.success,
        }


@dataclass
class OpenOrder:
    """A pending limit/stop order."""
    order_id: str
    request: TradeRequest
    status: OrderStatus = OrderStatus.SUBMITTED
    created_at: float = field(default_factory=time.time)
    fills: list[TradeResult] = field(default_factory=list)

    @property
    def is_active(self) -> bool:
        return self.status in (OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED)

    @property
    def age_hours(self) -> float:
        return (time.time() - self.created_at) / 3600

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "request": self.request.to_dict(),
            "status": self.status.value,
            "age_hours": round(self.age_hours, 1),
            "fill_count": len(self.fills),
        }


class TradingEngine:
    """Manages trade execution through Emblem Vault.

    The engine handles:
    1. Trade validation (sufficient balance, valid pairs).
    2. Approval gating (auto-approve small, confirm large).
    3. Execution via Emblem Vault API.
    4. Order tracking for limit/stop orders.
    5. Trade history.
    """

    def __init__(
        self,
        auto_approve_below: float = 10.0,
        require_confirmation_above: float = 100.0,
    ) -> None:
        self._auto_approve = auto_approve_below
        self._confirm_above = require_confirmation_above
        self._open_orders: dict[str, OpenOrder] = {}
        self._trade_history: list[TradeResult] = []
        self._pending_approvals: dict[str, TradeRequest] = {}

    async def submit_trade(self, request: TradeRequest) -> TradeResult | str:
        """Submit a trade request.

        Returns TradeResult if auto-approved and executed,
        or a string message if confirmation is required.
        """
        # Validate.
        validation = self._validate_trade(request)
        if validation:
            return TradeResult(
                request_id=request.id,
                status=OrderStatus.FAILED,
                error=validation,
            )

        # Check approval threshold.
        estimated_usd = await self._estimate_usd_value(request)
        if estimated_usd > self._confirm_above:
            self._pending_approvals[request.id] = request
            return (
                f"Trade requires confirmation: {request.describe()}\n"
                f"Estimated value: ${estimated_usd:,.2f}\n"
                f"Reply 'confirm {request.id}' to execute or 'cancel {request.id}' to cancel."
            )

        # Execute.
        return await self._execute_trade(request)

    async def confirm_trade(self, request_id: str) -> TradeResult:
        """Confirm a pending trade."""
        request = self._pending_approvals.pop(request_id, None)
        if not request:
            return TradeResult(
                request_id=request_id,
                status=OrderStatus.FAILED,
                error="No pending trade with that ID.",
            )
        return await self._execute_trade(request)

    async def cancel_trade(self, request_id: str) -> str:
        """Cancel a pending trade or open order."""
        if request_id in self._pending_approvals:
            req = self._pending_approvals.pop(request_id)
            return f"Cancelled: {req.describe()}"

        if request_id in self._open_orders:
            order = self._open_orders.pop(request_id)
            order.status = OrderStatus.CANCELLED
            return f"Cancelled order: {order.request.describe()}"

        return "No pending trade or order found with that ID."

    def get_open_orders(self) -> list[OpenOrder]:
        """Get all active open orders."""
        return [o for o in self._open_orders.values() if o.is_active]

    def get_trade_history(self, limit: int = 20) -> list[TradeResult]:
        """Get recent trade history."""
        return self._trade_history[-limit:]

    def get_pending_approvals(self) -> list[TradeRequest]:
        """Get trades waiting for confirmation."""
        return list(self._pending_approvals.values())

    # ---- Private ----

    def _validate_trade(self, request: TradeRequest) -> Optional[str]:
        """Validate a trade request. Returns error string or None."""
        if request.amount <= 0:
            return "Amount must be positive."
        if request.from_token == request.to_token:
            return "Cannot swap a token for itself."
        if request.slippage_bps > 1000:
            return "Slippage too high (max 10%)."
        if request.is_limit and request.limit_price is None:
            return "Limit orders require a price."
        return None

    async def _estimate_usd_value(self, request: TradeRequest) -> float:
        """Estimate the USD value of a trade."""
        # Would call price API. Return 0 as placeholder.
        return 0.0

    async def _execute_trade(self, request: TradeRequest) -> TradeResult:
        """Execute a trade through Emblem Vault."""
        # This would call the Emblem Vault swap API:
        # POST https://api.emblemvault.io/v1/swap
        # {
        #     "chain": request.chain.value,
        #     "from_token": request.from_token,
        #     "to_token": request.to_token,
        #     "amount": str(request.amount),
        #     "slippage_bps": request.slippage_bps,
        #     "password": self._wallet_password,
        # }

        if request.is_limit:
            order = OpenOrder(
                order_id=request.id,
                request=request,
            )
            self._open_orders[request.id] = order
            return TradeResult(
                request_id=request.id,
                status=OrderStatus.SUBMITTED,
            )

        # Market order — would execute immediately via API.
        result = TradeResult(
            request_id=request.id,
            status=OrderStatus.SUBMITTED,
        )
        self._trade_history.append(result)
        return result
