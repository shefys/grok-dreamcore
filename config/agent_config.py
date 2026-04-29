"""
Emblem AI — agent configuration and core setup.

Loads environment, initializes the LLM provider, memory store,
skill registry, and gateway connections. This is the entrypoint
configuration that the Hermes agent runtime reads on startup.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Optional
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass
class LLMConfig:
    """LLM provider configuration."""
    provider: str = "openrouter"
    api_key: str = ""
    model: str = "nousresearch/hermes-3-llama-3.1-405b"
    temperature: float = 0.7
    max_tokens: int = 4096
    system_prompt: str = ""

    @classmethod
    def from_env(cls) -> "LLMConfig":
        return cls(
            provider=os.getenv("LLM_PROVIDER", "openrouter"),
            api_key=os.getenv("OPENROUTER_API_KEY", ""),
            model=os.getenv("LLM_MODEL", "nousresearch/hermes-3-llama-3.1-405b"),
        )


@dataclass
class EmblemConfig:
    """Emblem Vault integration configuration."""
    api_key: str = ""
    wallet_password: str = ""
    default_chain: str = "solana"
    supported_chains: list[str] = field(default_factory=lambda: [
        "solana", "ethereum", "base", "bsc", "polygon", "hedera", "bitcoin"
    ])
    auto_approve_below: float = 10.0  # Auto-approve transactions below $10.
    require_confirmation_above: float = 100.0  # Always confirm above $100.

    @classmethod
    def from_env(cls) -> "EmblemConfig":
        return cls(
            api_key=os.getenv("EMBLEM_API_KEY", ""),
            wallet_password=os.getenv("EMBLEM_WALLET_PASSWORD", ""),
            default_chain=os.getenv("EMBLEM_DEFAULT_CHAIN", "solana"),
        )


@dataclass
class MemoryConfig:
    """Memory and persistence configuration."""
    db_path: str = "./memory_store/emblem_ai.db"
    search_limit: int = 10
    decay_rate: float = 0.02
    max_context_memories: int = 8
    auto_memorize: bool = True
    nudge_interval_minutes: int = 30

    @classmethod
    def from_env(cls) -> "MemoryConfig":
        return cls(
            db_path=os.getenv("MEMORY_DB_PATH", "./memory_store/emblem_ai.db"),
            search_limit=int(os.getenv("MEMORY_SEARCH_LIMIT", "10")),
        )


@dataclass
class GatewayConfig:
    """Multi-platform gateway configuration."""
    telegram_token: str = ""
    discord_token: str = ""
    enabled_platforms: list[str] = field(default_factory=lambda: ["cli"])

    @classmethod
    def from_env(cls) -> "GatewayConfig":
        platforms = ["cli"]
        tg = os.getenv("TELEGRAM_BOT_TOKEN", "")
        dc = os.getenv("DISCORD_BOT_TOKEN", "")
        if tg:
            platforms.append("telegram")
        if dc:
            platforms.append("discord")
        return cls(
            telegram_token=tg,
            discord_token=dc,
            enabled_platforms=platforms,
        )


@dataclass
class AgentConfig:
    """Top-level agent configuration."""
    name: str = "Emblem AI"
    owner: str = "Adam McBride"
    persona: str = (
        "You are Emblem AI, Adam McBride's personal Hermes agent. "
        "You handle crypto portfolio management, research, scheduling, "
        "and general assistance. You are powered by Emblem Vault for "
        "multi-chain crypto operations across 7 blockchains. "
        "You are direct, concise, and proactive. You remember context "
        "across sessions and build skills from experience. "
        "When handling crypto, you always confirm transactions above $100 "
        "and flag unusual market conditions."
    )
    llm: LLMConfig = field(default_factory=LLMConfig)
    emblem: EmblemConfig = field(default_factory=EmblemConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    gateway: GatewayConfig = field(default_factory=GatewayConfig)
    skills_dir: str = "./skills"
    workflows_dir: str = "./workflows"

    @classmethod
    def load(cls) -> "AgentConfig":
        return cls(
            llm=LLMConfig.from_env(),
            emblem=EmblemConfig.from_env(),
            memory=MemoryConfig.from_env(),
            gateway=GatewayConfig.from_env(),
        )

    def validate(self) -> list[str]:
        """Return list of warnings for missing config."""
        warnings: list[str] = []
        if not self.llm.api_key:
            warnings.append("No LLM API key set (OPENROUTER_API_KEY)")
        if not self.emblem.api_key:
            warnings.append("No Emblem API key set (EMBLEM_API_KEY)")
        if not self.emblem.wallet_password:
            warnings.append("No Emblem wallet password set")
        return warnings

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "owner": self.owner,
            "llm_provider": self.llm.provider,
            "llm_model": self.llm.model,
            "default_chain": self.emblem.default_chain,
            "supported_chains": self.emblem.supported_chains,
            "memory_db": self.memory.db_path,
            "gateway_platforms": self.gateway.enabled_platforms,
        }
