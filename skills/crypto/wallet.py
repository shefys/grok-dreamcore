"""
Crypto wallet skill — multi-chain wallet operations via Emblem Vault.

Handles balance checks, token lookups, wallet creation, and
basic account management across all supported chains.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum


class Chain(Enum):
    SOLANA = "solana"
    ETHEREUM = "ethereum"
    BASE = "base"
    BSC = "bsc"
    POLYGON = "polygon"
    HEDERA = "hedera"
    BITCOIN = "bitcoin"

    @classmethod
    def from_name(cls, name: str) -> "Chain":
        name_lower = name.lower().strip()
        aliases = {
            "sol": cls.SOLANA, "eth": cls.ETHEREUM, "ether": cls.ETHEREUM,
            "bsc": cls.BSC, "bnb": cls.BSC, "poly": cls.POLYGON,
            "matic": cls.POLYGON, "btc": cls.BITCOIN, "hbar": cls.HEDERA,
        }
        if name_lower in aliases:
            return aliases[name_lower]
        for member in cls:
            if member.value == name_lower:
                return member
        raise ValueError(f"Unknown chain: {name}")


@dataclass
class TokenBalance:
    """A single token balance entry."""
    symbol: str
    name: str
    balance: float
    usd_value: float
    chain: Chain
    mint_address: Optional[str] = None
    decimals: int = 9
    price_usd: float = 0.0
    change_24h: float = 0.0

    @property
    def is_native(self) -> bool:
        native_symbols = {"SOL", "ETH", "BNB", "MATIC", "HBAR", "BTC"}
        return self.symbol.upper() in native_symbols

    def format_balance(self) -> str:
        if self.balance >= 1_000_000:
            return f"{self.balance / 1_000_000:.2f}M"
        elif self.balance >= 1_000:
            return f"{self.balance / 1_000:.2f}K"
        return f"{self.balance:.4f}"

    def format_usd(self) -> str:
        if self.usd_value >= 1_000:
            return f"${self.usd_value:,.2f}"
        return f"${self.usd_value:.2f}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "balance": self.balance,
            "usd_value": self.usd_value,
            "chain": self.chain.value,
            "price_usd": self.price_usd,
            "change_24h": self.change_24h,
        }


@dataclass
class WalletSummary:
    """Summary of all balances across chains."""
    balances: list[TokenBalance] = field(default_factory=list)
    total_usd: float = 0.0
    chain_breakdown: dict[str, float] = field(default_factory=dict)
    last_updated: float = field(default_factory=time.time)

    def by_chain(self, chain: Chain) -> list[TokenBalance]:
        return [b for b in self.balances if b.chain == chain]

    def by_value(self, min_usd: float = 0.01) -> list[TokenBalance]:
        return sorted(
            [b for b in self.balances if b.usd_value >= min_usd],
            key=lambda b: b.usd_value,
            reverse=True,
        )

    def top_holdings(self, n: int = 5) -> list[TokenBalance]:
        return self.by_value()[:n]

    def format_summary(self) -> str:
        lines = [f"Portfolio: {self.format_total()}"]
        for chain_name, value in sorted(
            self.chain_breakdown.items(), key=lambda x: x[1], reverse=True
        ):
            pct = (value / self.total_usd * 100) if self.total_usd > 0 else 0
            lines.append(f"  {chain_name}: ${value:,.2f} ({pct:.1f}%)")
        return "\n".join(lines)

    def format_total(self) -> str:
        return f"${self.total_usd:,.2f}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_usd": self.total_usd,
            "chain_breakdown": self.chain_breakdown,
            "holding_count": len(self.balances),
            "top_5": [b.to_dict() for b in self.top_holdings()],
        }


class EmblemWalletClient:
    """Client for Emblem Vault wallet operations.

    Wraps the Emblem Vault API for wallet management.
    All operations are read-only except for explicitly
    authorized transactions.
    """

    def __init__(self, api_key: str, wallet_password: str, default_chain: str = "solana") -> None:
        self._api_key = api_key
        self._wallet_password = wallet_password
        self._default_chain = Chain.from_name(default_chain)
        self._cache: dict[str, Any] = {}
        self._cache_ttl = 30  # seconds

    async def get_balances(self, chain: Optional[Chain] = None) -> list[TokenBalance]:
        """Fetch token balances for a specific chain or all chains."""
        target_chains = [chain] if chain else list(Chain)
        all_balances: list[TokenBalance] = []

        for c in target_chains:
            balances = await self._fetch_chain_balances(c)
            all_balances.extend(balances)

        return all_balances

    async def get_wallet_summary(self) -> WalletSummary:
        """Get a complete portfolio summary across all chains."""
        balances = await self.get_balances()
        total_usd = sum(b.usd_value for b in balances)
        chain_breakdown: dict[str, float] = {}
        for b in balances:
            chain_name = b.chain.value
            chain_breakdown[chain_name] = chain_breakdown.get(chain_name, 0) + b.usd_value

        return WalletSummary(
            balances=balances,
            total_usd=total_usd,
            chain_breakdown=chain_breakdown,
        )

    async def get_token_price(self, symbol: str, chain: Optional[Chain] = None) -> Optional[float]:
        """Get current USD price for a token."""
        # Would call Emblem Vault's price API.
        # Placeholder for the actual API call.
        return None

    async def get_wallet_address(self, chain: Optional[Chain] = None) -> str:
        """Get the wallet address for a specific chain."""
        target = chain or self._default_chain
        # Deterministic wallet from Emblem Vault.
        return f"<{target.value}_wallet_address>"

    async def _fetch_chain_balances(self, chain: Chain) -> list[TokenBalance]:
        """Fetch balances for a single chain from Emblem Vault API."""
        cache_key = f"balances:{chain.value}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        # This would be the actual Emblem Vault API call:
        # POST https://api.emblemvault.io/v1/wallet/balances
        # { "chain": chain.value, "password": self._wallet_password }
        #
        # For now, return empty — the real API fills this in at runtime.
        balances: list[TokenBalance] = []
        self._set_cached(cache_key, balances)
        return balances

    def _get_cached(self, key: str) -> Any:
        entry = self._cache.get(key)
        if entry and (time.time() - entry["time"]) < self._cache_ttl:
            return entry["data"]
        return None

    def _set_cached(self, key: str, data: Any) -> None:
        self._cache[key] = {"data": data, "time": time.time()}
