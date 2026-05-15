"""
Emblem AI — main agent entry point.

Initializes all subsystems and starts the agent loop.
The agent processes messages from connected platforms,
maintains memory across sessions, and runs scheduled
automations in the background.

Usage:
    python -m emblem_ai         # Start in CLI mode
    python -m emblem_ai --setup # Run setup wizard
"""

from __future__ import annotations

import asyncio
import sys
from typing import Optional

from config.agent_config import AgentConfig
from config.persona import ADAM_PERSONA
from memory.store import MemoryStore, MemoryEntry, MemoryType
from gateway.adapters import (
    Gateway, CLIAdapter, TelegramAdapter, DiscordAdapter,
    IncomingMessage, OutgoingMessage, Platform,
)
from skills.crypto.wallet import EmblemWalletClient
from skills.crypto.trading import TradingEngine
from skills.crypto.bridge import BridgeEngine
from skills.portfolio.tracker import PortfolioTracker
from skills.research.market import ResearchEngine
from skills.assistant.tasks import TaskManager
from skills.scheduling.scheduler import Scheduler
from workflows.automations import WorkflowEngine
from tools.llm_client import LLMClient


class EmblemAgent:
    """The main agent orchestrator.

    Ties together all subsystems: LLM, memory, crypto tools,
    portfolio tracking, scheduling, and multi-platform gateway.
    """

    def __init__(self, config: Optional[AgentConfig] = None) -> None:
        self._config = config or AgentConfig.load()
        self._persona = ADAM_PERSONA

        # Core.
        self._llm = LLMClient(
            provider=self._config.llm.provider,
            api_key=self._config.llm.api_key,
            model=self._config.llm.model,
        )
        self._memory = MemoryStore(self._config.memory.db_path)

        # Skills.
        self._wallet = EmblemWalletClient(
            api_key=self._config.emblem.api_key,
            wallet_password=self._config.emblem.wallet_password,
            default_chain=self._config.emblem.default_chain,
        )
        self._trading = TradingEngine(
            auto_approve_below=self._config.emblem.auto_approve_below,
            require_confirmation_above=self._config.emblem.require_confirmation_above,
        )
        self._bridge = BridgeEngine()
        self._portfolio = PortfolioTracker()
        self._research = ResearchEngine()
        self._tasks = TaskManager()
        self._scheduler = Scheduler()

        # Workflows.
        self._workflows = WorkflowEngine(
            portfolio=self._portfolio,
            tasks=self._tasks,
            research=self._research,
        )

        # Gateway.
        self._gateway = Gateway()

        # Session.
        self._session_id = f"session_{int(asyncio.get_event_loop().time())}"
        self._message_count = 0

    async def start(self) -> None:
        """Start the agent."""
        # Validate config.
        warnings = self._config.validate()
        for warning in warnings:
            print(f"[warning] {warning}")

        # Register platform adapters.
        self._gateway.register(CLIAdapter())

        if self._config.gateway.telegram_token:
            self._gateway.register(
                TelegramAdapter(self._config.gateway.telegram_token)
            )
        if self._config.gateway.discord_token:
            self._gateway.register(
                DiscordAdapter(self._config.gateway.discord_token)
            )

        # Register workflow handlers with scheduler.
        self._scheduler.register_handler(
            "daily_briefing", self._workflows.morning_briefing
        )
        self._scheduler.register_handler(
            "portfolio_snapshot", self._workflows.portfolio_snapshot
        )
        self._scheduler.register_handler(
            "news_digest", self._workflows.news_digest
        )

        print(f"Emblem AI v{self._config.name}")
        print(f"Owner: {self._config.owner}")
        print(f"LLM: {self._config.llm.model}")
        print(f"Platforms: {', '.join(self._gateway.platforms)}")
        print(f"Memory: {self._memory.stats()['total_memories']} memories")
        print()

        # Start message loop.
        await self._gateway.start_all(self._handle_message)

    async def _handle_message(self, message: IncomingMessage) -> OutgoingMessage:
        """Process an incoming message and generate a response."""
        self._message_count += 1

        # Store conversation.
        self._memory.store_conversation(
            self._session_id, "user", message.text
        )

        # Retrieve relevant memories.
        memories = self._memory.search(message.text, limit=self._config.memory.max_context_memories)
        memory_context = ""
        if memories:
            memory_parts = [f"- {m.summary}" for m in memories]
            memory_context = "\nRelevant memories:\n" + "\n".join(memory_parts)

        # Build messages for LLM.
        conversation = self._memory.get_conversation(self._session_id, limit=20)
        system_prompt = self._persona.build_system_prompt() + memory_context

        # Get LLM response.
        try:
            response = await self._llm.complete(
                messages=conversation,
                system=system_prompt,
            )
            response_text = response.text
        except Exception as e:
            response_text = f"Error contacting LLM: {e}"

        # Store response in conversation.
        self._memory.store_conversation(
            self._session_id, "assistant", response_text
        )

        # Auto-memorize if the message seems important.
        if self._config.memory.auto_memorize:
            self._auto_memorize(message.text, response_text)

        return OutgoingMessage(
            text=response_text,
            platform=message.platform,
            channel_id=message.channel_id,
            reply_to=message.user_id,
        )

    def _auto_memorize(self, user_msg: str, agent_msg: str) -> None:
        """Automatically store important interactions as memories."""
        importance_markers = [
            "remember", "don't forget", "important", "always",
            "never", "prefer", "i like", "i hate", "my wallet",
            "my address", "password", "schedule", "remind me",
        ]
        msg_lower = user_msg.lower()

        if any(marker in msg_lower for marker in importance_markers):
            self._memory.store(MemoryEntry(
                content=f"User said: {user_msg[:200]}",
                memory_type=MemoryType.PREFERENCE,
                salience=0.8,
                source="auto_memorize",
                tags=["preference", "user_stated"],
            ))

    async def shutdown(self) -> None:
        """Clean shutdown."""
        await self._gateway.stop_all()
        await self._llm.close()
        self._memory.close()
        print("Emblem AI shut down.")


async def main() -> None:
    agent = EmblemAgent()

    try:
        await agent.start()
    except KeyboardInterrupt:
        pass
    finally:
        await agent.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
