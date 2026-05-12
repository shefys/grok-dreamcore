"""
Gateway — multi-platform messaging interface.

Routes messages between the agent and external platforms
(Telegram, Discord, CLI). Each platform adapter normalizes
messages into a common format for the agent to process.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional, Callable, Awaitable
from enum import Enum


class Platform(Enum):
    CLI = "cli"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    X = "x"


@dataclass
class IncomingMessage:
    """A normalized incoming message from any platform."""
    text: str
    platform: Platform
    user_id: str
    user_name: str
    channel_id: str = ""
    reply_to: Optional[str] = None
    attachments: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    raw: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "platform": self.platform.value,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "timestamp": self.timestamp,
        }


@dataclass
class OutgoingMessage:
    """A response to send back to a platform."""
    text: str
    platform: Platform
    channel_id: str = ""
    reply_to: Optional[str] = None
    parse_mode: str = "plain"  # "plain", "markdown", "html"

    def truncate(self, max_length: int = 4096) -> "OutgoingMessage":
        if len(self.text) <= max_length:
            return self
        return OutgoingMessage(
            text=self.text[:max_length - 3] + "...",
            platform=self.platform,
            channel_id=self.channel_id,
            reply_to=self.reply_to,
            parse_mode=self.parse_mode,
        )


MessageHandler = Callable[[IncomingMessage], Awaitable[OutgoingMessage]]


class PlatformAdapter(ABC):
    """Base class for platform adapters."""

    @abstractmethod
    async def start(self, handler: MessageHandler) -> None:
        """Start listening for messages."""
        ...

    @abstractmethod
    async def send(self, message: OutgoingMessage) -> None:
        """Send a message to the platform."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Stop the adapter."""
        ...

    @property
    @abstractmethod
    def platform(self) -> Platform:
        ...


class CLIAdapter(PlatformAdapter):
    """CLI adapter for local development and testing."""

    def __init__(self) -> None:
        self._running = False
        self._handler: Optional[MessageHandler] = None

    @property
    def platform(self) -> Platform:
        return Platform.CLI

    async def start(self, handler: MessageHandler) -> None:
        self._handler = handler
        self._running = True

        print("Emblem AI CLI — type 'exit' to quit\n")
        while self._running:
            try:
                user_input = input("you > ").strip()
            except (EOFError, KeyboardInterrupt):
                break

            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit"):
                break

            message = IncomingMessage(
                text=user_input,
                platform=Platform.CLI,
                user_id="cli_user",
                user_name="Adam",
            )

            response = await self._handler(message)
            print(f"\nemblem > {response.text}\n")

    async def send(self, message: OutgoingMessage) -> None:
        print(f"emblem > {message.text}")

    async def stop(self) -> None:
        self._running = False


class TelegramAdapter(PlatformAdapter):
    """Telegram bot adapter using python-telegram-bot."""

    def __init__(self, token: str) -> None:
        self._token = token
        self._handler: Optional[MessageHandler] = None
        self._app: Any = None

    @property
    def platform(self) -> Platform:
        return Platform.TELEGRAM

    async def start(self, handler: MessageHandler) -> None:
        self._handler = handler

        try:
            from telegram.ext import Application, MessageHandler as TGHandler, filters

            self._app = Application.builder().token(self._token).build()

            async def on_message(update: Any, context: Any) -> None:
                if not update.message or not update.message.text:
                    return
                msg = IncomingMessage(
                    text=update.message.text,
                    platform=Platform.TELEGRAM,
                    user_id=str(update.effective_user.id),
                    user_name=update.effective_user.first_name or "",
                    channel_id=str(update.effective_chat.id),
                    raw=update,
                )
                response = await self._handler(msg)  # type: ignore
                await update.message.reply_text(
                    response.text,
                    parse_mode="Markdown" if response.parse_mode == "markdown" else None,
                )

            self._app.add_handler(TGHandler(filters.TEXT & ~filters.COMMAND, on_message))
            await self._app.run_polling()
        except ImportError:
            raise ImportError("Install python-telegram-bot: pip install python-telegram-bot")

    async def send(self, message: OutgoingMessage) -> None:
        if self._app and message.channel_id:
            await self._app.bot.send_message(
                chat_id=message.channel_id,
                text=message.text,
            )

    async def stop(self) -> None:
        if self._app:
            await self._app.stop()


class DiscordAdapter(PlatformAdapter):
    """Discord bot adapter."""

    def __init__(self, token: str) -> None:
        self._token = token
        self._handler: Optional[MessageHandler] = None
        self._client: Any = None

    @property
    def platform(self) -> Platform:
        return Platform.DISCORD

    async def start(self, handler: MessageHandler) -> None:
        self._handler = handler

        try:
            import discord

            intents = discord.Intents.default()
            intents.message_content = True
            self._client = discord.Client(intents=intents)

            @self._client.event
            async def on_message(dc_message: Any) -> None:
                if dc_message.author == self._client.user:
                    return
                if not self._client.user or self._client.user.mentioned_in(dc_message):
                    msg = IncomingMessage(
                        text=dc_message.content,
                        platform=Platform.DISCORD,
                        user_id=str(dc_message.author.id),
                        user_name=dc_message.author.display_name,
                        channel_id=str(dc_message.channel.id),
                        raw=dc_message,
                    )
                    response = await self._handler(msg)  # type: ignore
                    await dc_message.channel.send(response.text)

            await self._client.start(self._token)
        except ImportError:
            raise ImportError("Install discord.py: pip install discord.py")

    async def send(self, message: OutgoingMessage) -> None:
        pass  # Direct sends handled in on_message.

    async def stop(self) -> None:
        if self._client:
            await self._client.close()


class Gateway:
    """Manages multiple platform adapters."""

    def __init__(self) -> None:
        self._adapters: dict[Platform, PlatformAdapter] = {}

    def register(self, adapter: PlatformAdapter) -> None:
        self._adapters[adapter.platform] = adapter

    async def start_all(self, handler: MessageHandler) -> None:
        """Start all registered adapters."""
        import asyncio
        tasks = [adapter.start(handler) for adapter in self._adapters.values()]
        await asyncio.gather(*tasks)

    async def stop_all(self) -> None:
        for adapter in self._adapters.values():
            await adapter.stop()

    @property
    def platforms(self) -> list[str]:
        return [p.value for p in self._adapters.keys()]
