"""OpenAI-compatible embeddings: api.openai.com по умолчанию или прокси по OPENAI_BASE_URL."""

from __future__ import annotations

import asyncio
import os

import numpy as np
from loguru import logger
from openai import AsyncOpenAI

from config import config

# Аналогично client.py: пустая OPENAI_BASE_URL из systemd EnvironmentFile сломает SDK.
if "OPENAI_BASE_URL" in os.environ and not os.environ["OPENAI_BASE_URL"].strip():
    del os.environ["OPENAI_BASE_URL"]


class EmbeddingsClient:
    def __init__(self) -> None:
        self.client = AsyncOpenAI(
            api_key=config.OPENAI_API_KEY or "dummy",
            base_url=config.OPENAI_BASE_URL or None,
        )
        self.model = config.EMBEDDINGS_MODEL

    async def create(self, text: str) -> np.ndarray:
        """Один вектор float32."""
        vecs = await self.create_batch([text])
        return vecs[0]

    async def create_batch(self, texts: list[str]) -> list[np.ndarray]:
        """Батч эмбеддингов."""
        if not texts:
            return []
        inputs = [t[:8000] for t in texts]
        delays = [0.0, 1.0, 2.0, 4.0]
        last_err: Exception | None = None
        for attempt, delay in enumerate(delays):
            if delay:
                await asyncio.sleep(delay)
            try:
                resp = await self.client.embeddings.create(model=self.model, input=inputs)
                out = [np.array(d.embedding, dtype=np.float32) for d in resp.data]
                logger.debug("embeddings batch n={} model={}", len(texts), self.model)
                return out
            except Exception as e:  # noqa: BLE001
                last_err = e
                logger.warning("embeddings attempt {} failed: {}", attempt + 1, e)
        assert last_err is not None
        raise last_err
