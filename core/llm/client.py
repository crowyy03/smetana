"""Обёртка над Anthropic Async SDK: retry, fallback, JSON."""

from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass

import anthropic
from loguru import logger

from config import config

# SDK Anthropic читает ANTHROPIC_BASE_URL из os.environ когда base_url=None.
# systemd через EnvironmentFile=.env инжектит пустую строку, и SDK берёт её как URL → connection error.
# Удаляем переменную, если она пустая, ещё до создания клиента.
if "ANTHROPIC_BASE_URL" in os.environ and not os.environ["ANTHROPIC_BASE_URL"].strip():
    del os.environ["ANTHROPIC_BASE_URL"]


class LLMParseError(Exception):
    pass


@dataclass
class LLMResponse:
    content: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


def _estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    # грубые ориентиры для логов (не официальный биллинг)
    rates = {
        "claude-sonnet-4-6": (3.0 / 1e6, 15.0 / 1e6),
        "claude-opus-4-6": (15.0 / 1e6, 75.0 / 1e6),
    }
    inp_r, out_r = rates.get(model, (5.0 / 1e6, 25.0 / 1e6))
    return input_tokens * inp_r + output_tokens * out_r


class LLMClient:
    def __init__(self) -> None:
        self.client = anthropic.AsyncAnthropic(
            api_key=config.ANTHROPIC_API_KEY or "dummy",
            base_url=config.ANTHROPIC_BASE_URL or None,
            timeout=60.0,
        )
        self.primary_model = config.PRIMARY_MODEL
        self.fallback_model = config.FALLBACK_MODEL

    async def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 4096,
        temperature: float = 0,
        use_fallback: bool = False,
    ) -> LLMResponse:
        model = self.fallback_model if use_fallback else self.primary_model
        last_err: Exception | None = None
        delays = [1.0, 2.0, 4.0]

        for attempt, delay in enumerate([0.0] + delays):
            if delay:
                await asyncio.sleep(delay)
            try:
                msg = await self.client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                )
                text_parts: list[str] = []
                for block in msg.content:
                    if hasattr(block, "text"):
                        text_parts.append(block.text)
                content = "".join(text_parts)
                in_tok = getattr(msg.usage, "input_tokens", 0) or 0
                out_tok = getattr(msg.usage, "output_tokens", 0) or 0
                cost = _estimate_cost_usd(model, in_tok, out_tok)
                logger.info(
                    "LLM ok model={} in={} out={} cost~${:.4f}",
                    model,
                    in_tok,
                    out_tok,
                    cost,
                )
                return LLMResponse(
                    content=content,
                    model=model,
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    cost_usd=cost,
                )
            except Exception as e:  # noqa: BLE001
                last_err = e
                logger.warning("LLM attempt {} failed: {}", attempt + 1, e)

        if not use_fallback and self.fallback_model != self.primary_model:
            logger.warning("Trying fallback model {}", self.fallback_model)
            return await self.complete(
                system,
                user,
                max_tokens=max_tokens,
                temperature=temperature,
                use_fallback=True,
            )

        assert last_err is not None
        raise last_err

    async def complete_json(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 4096,
        temperature: float = 0,
        use_fallback: bool = False,
    ) -> dict:
        resp = await self.complete(
            system,
            user,
            max_tokens=max_tokens,
            temperature=temperature,
            use_fallback=use_fallback,
        )
        raw = resp.content.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```\s*$", "", raw)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error("LLM JSON parse error: {} raw={}", e, raw[:2000])
            raise LLMParseError(str(e)) from e
