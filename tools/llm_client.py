"""
LLM client — interfaces with language model providers.

Supports OpenRouter (200+ models), Nous Portal, OpenAI,
and Anthropic. The agent can switch between providers
without code changes.
"""

from __future__ import annotations

import json
from typing import Any, Optional
from dataclasses import dataclass, field

import httpx


@dataclass
class LLMResponse:
    """Response from an LLM completion."""
    text: str
    model: str
    tokens_used: int = 0
    finish_reason: str = ""
    latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text[:200],
            "model": self.model,
            "tokens_used": self.tokens_used,
            "finish_reason": self.finish_reason,
            "latency_ms": round(self.latency_ms, 1),
        }


class LLMClient:
    """Multi-provider LLM client."""

    PROVIDER_URLS = {
        "openrouter": "https://openrouter.ai/api/v1/chat/completions",
        "openai": "https://api.openai.com/v1/chat/completions",
        "anthropic": "https://api.anthropic.com/v1/messages",
        "nous": "https://inference-api.nousresearch.com/v1/chat/completions",
    }

    def __init__(
        self,
        provider: str = "openrouter",
        api_key: str = "",
        model: str = "nousresearch/hermes-3-llama-3.1-405b",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> None:
        self._provider = provider
        self._api_key = api_key
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._client = httpx.AsyncClient(timeout=60.0)

    async def complete(
        self,
        messages: list[dict[str, str]],
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """Send a chat completion request."""
        import time
        start = time.time()

        if self._provider == "anthropic":
            return await self._complete_anthropic(messages, system, temperature, max_tokens, start)

        # OpenAI-compatible providers (OpenRouter, OpenAI, Nous).
        url = self.PROVIDER_URLS.get(self._provider, self.PROVIDER_URLS["openrouter"])
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        if self._provider == "openrouter":
            headers["HTTP-Referer"] = "https://github.com/Adam-McBride/Emblem-AI"
            headers["X-Title"] = "Emblem AI"

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages if not system else [{"role": "system", "content": system}] + messages,
            "temperature": temperature or self._temperature,
            "max_tokens": max_tokens or self._max_tokens,
        }

        response = await self._client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

        choice = data["choices"][0]
        return LLMResponse(
            text=choice["message"]["content"],
            model=data.get("model", self._model),
            tokens_used=data.get("usage", {}).get("total_tokens", 0),
            finish_reason=choice.get("finish_reason", ""),
            latency_ms=(time.time() - start) * 1000,
        )

    async def _complete_anthropic(
        self,
        messages: list[dict[str, str]],
        system: Optional[str],
        temperature: Optional[float],
        max_tokens: Optional[int],
        start: float,
    ) -> LLMResponse:
        """Anthropic-specific completion."""
        import time
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens or self._max_tokens,
            "temperature": temperature or self._temperature,
        }
        if system:
            payload["system"] = system

        response = await self._client.post(
            self.PROVIDER_URLS["anthropic"],
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

        text = data["content"][0]["text"] if data.get("content") else ""
        return LLMResponse(
            text=text,
            model=data.get("model", self._model),
            tokens_used=data.get("usage", {}).get("input_tokens", 0) + data.get("usage", {}).get("output_tokens", 0),
            finish_reason=data.get("stop_reason", ""),
            latency_ms=(time.time() - start) * 1000,
        )

    async def close(self) -> None:
        await self._client.aclose()
