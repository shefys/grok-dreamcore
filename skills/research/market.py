"""
Research skill — token lookup, market data, and news aggregation.

Provides tools for the agent to research tokens, track market
conditions, and aggregate crypto news for the owner.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

from skills.crypto.wallet import Chain


@dataclass
class TokenInfo:
    """Detailed information about a token."""
    symbol: str
    name: str
    chain: Chain
    price_usd: float = 0.0
    market_cap: float = 0.0
    volume_24h: float = 0.0
    change_24h: float = 0.0
    change_7d: float = 0.0
    holders: int = 0
    liquidity_usd: float = 0.0
    contract_address: Optional[str] = None
    dex_url: Optional[str] = None
    is_verified: bool = False
    risk_score: float = 0.0  # 0=safe, 1=dangerous

    def format_price(self) -> str:
        if self.price_usd >= 1.0:
            return f"${self.price_usd:,.2f}"
        elif self.price_usd >= 0.001:
            return f"${self.price_usd:.4f}"
        return f"${self.price_usd:.8f}"

    def format_summary(self) -> str:
        lines = [
            f"{self.name} ({self.symbol}) — {self.chain.value}",
            f"Price: {self.format_price()} ({self.change_24h:+.1f}% 24h)",
            f"MCap: ${self.market_cap:,.0f}" if self.market_cap > 0 else "MCap: N/A",
            f"Vol 24h: ${self.volume_24h:,.0f}" if self.volume_24h > 0 else "Vol: N/A",
            f"Holders: {self.holders:,}" if self.holders > 0 else "",
            f"Verified: {'yes' if self.is_verified else 'no'}",
        ]
        if self.risk_score > 0.5:
            lines.append(f"RISK: {self.risk_score:.1f}/1.0")
        return "\n".join(line for line in lines if line)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "chain": self.chain.value,
            "price_usd": self.price_usd,
            "market_cap": self.market_cap,
            "volume_24h": self.volume_24h,
            "change_24h": self.change_24h,
            "holders": self.holders,
            "is_verified": self.is_verified,
            "risk_score": self.risk_score,
        }


@dataclass
class MarketOverview:
    """Broad market snapshot."""
    btc_price: float = 0.0
    eth_price: float = 0.0
    sol_price: float = 0.0
    btc_dominance: float = 0.0
    total_market_cap: float = 0.0
    fear_greed_index: int = 50
    trending_tokens: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def format_summary(self) -> str:
        fg_label = "Neutral"
        if self.fear_greed_index < 25:
            fg_label = "Extreme Fear"
        elif self.fear_greed_index < 40:
            fg_label = "Fear"
        elif self.fear_greed_index > 75:
            fg_label = "Extreme Greed"
        elif self.fear_greed_index > 60:
            fg_label = "Greed"

        lines = [
            "Market Overview:",
            f"  BTC: ${self.btc_price:,.0f} | ETH: ${self.eth_price:,.0f} | SOL: ${self.sol_price:,.0f}",
            f"  Total MCap: ${self.total_market_cap / 1e12:.2f}T | BTC Dom: {self.btc_dominance:.1f}%",
            f"  Fear/Greed: {self.fear_greed_index} ({fg_label})",
        ]
        if self.trending_tokens:
            lines.append(f"  Trending: {', '.join(self.trending_tokens[:5])}")
        return "\n".join(lines)


@dataclass
class NewsItem:
    """A single news item."""
    title: str
    source: str
    url: str
    summary: str = ""
    published_at: float = field(default_factory=time.time)
    relevance_score: float = 0.5
    tokens_mentioned: list[str] = field(default_factory=list)

    def format_brief(self) -> str:
        return f"[{self.source}] {self.title}"


class ResearchEngine:
    """Handles token research, market data, and news."""

    def __init__(self) -> None:
        self._token_cache: dict[str, TokenInfo] = {}
        self._cache_ttl = 60  # seconds
        self._cache_times: dict[str, float] = {}

    async def lookup_token(self, symbol: str, chain: Optional[Chain] = None) -> Optional[TokenInfo]:
        """Look up a token by symbol.

        Would call Emblem Vault's token info API or DexScreener.
        """
        cache_key = f"{symbol}:{chain.value if chain else 'any'}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        # Actual API call would go here:
        # GET https://api.emblemvault.io/v1/tokens/search?q={symbol}&chain={chain}
        # OR
        # GET https://api.dexscreener.com/latest/dex/search?q={symbol}
        return None

    async def get_market_overview(self) -> MarketOverview:
        """Get broad market snapshot.

        Would aggregate from CoinGecko / Emblem Vault market API.
        """
        return MarketOverview()

    async def get_news(self, limit: int = 5, token: Optional[str] = None) -> list[NewsItem]:
        """Get recent crypto news, optionally filtered by token."""
        # Would call a news aggregation API.
        return []

    async def check_token_safety(self, contract: str, chain: Chain) -> dict[str, Any]:
        """Run safety checks on a token contract.

        Checks for: honeypot, liquidity lock, ownership renounced,
        suspicious holder concentration, etc.
        """
        return {
            "contract": contract,
            "chain": chain.value,
            "is_honeypot": False,
            "liquidity_locked": False,
            "ownership_renounced": False,
            "top_holder_pct": 0.0,
            "risk_level": "unknown",
            "warnings": ["Safety check requires live API connection"],
        }

    def _get_cached(self, key: str) -> Optional[TokenInfo]:
        if key in self._token_cache:
            age = time.time() - self._cache_times.get(key, 0)
            if age < self._cache_ttl:
                return self._token_cache[key]
        return None
