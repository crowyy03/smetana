"""Поиск похожих ReferenceItem по cosine similarity."""

from __future__ import annotations

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import config
from core.llm.embeddings_client import EmbeddingsClient
from core.reference_db.synonyms import expand_synonyms
from db.models import ReferenceItem, ReferenceProject


class ReferenceRetriever:
    def __init__(self) -> None:
        self._items: list[ReferenceItem] = []
        self._embeddings: np.ndarray | None = None

    async def load_index(self, session: AsyncSession) -> None:
        r = await session.execute(
            select(ReferenceItem)
            .join(ReferenceProject)
            .where(ReferenceProject.is_active.is_(True), ReferenceItem.embedding.is_not(None))
            .options(selectinload(ReferenceItem.project))
        )
        self._items = list(r.scalars().all())
        if not self._items:
            self._embeddings = None
            return
        mats = []
        for it in self._items:
            vec = np.frombuffer(it.embedding, dtype=np.float32)  # type: ignore[arg-type]
            n = np.linalg.norm(vec)
            if n > 0:
                vec = vec / n
            mats.append(vec)
        self._embeddings = np.stack(mats, axis=0)

    async def find_similar(
        self,
        session: AsyncSession,
        query_text: str,
        top_k: int | None = None,
        category_filter: str | None = None,
    ) -> list[tuple[ReferenceItem, float]]:
        k = top_k or config.TOP_K_REFERENCES
        if not self._items or self._embeddings is None:
            await self.load_index(session)
        if not self._items or self._embeddings is None:
            return []

        emb_client = EmbeddingsClient()
        q = await emb_client.create(expand_synonyms(query_text))
        qn = np.linalg.norm(q)
        if qn > 0:
            q = q / qn
        scores = self._embeddings @ q

        if category_filter:
            mask = np.array([it.category == category_filter for it in self._items], dtype=np.float32)
            scores = np.where(mask > 0, scores, -1.0)

        top_indices = np.argsort(-scores)[:k]
        return [(self._items[int(i)], float(scores[int(i)])) for i in top_indices if scores[int(i)] > -0.5]

    @staticmethod
    def confidence_level(score: float) -> str:
        if score >= config.HIGH_CONFIDENCE_THRESHOLD:
            return "high"
        if score >= config.MEDIUM_CONFIDENCE_THRESHOLD:
            return "medium"
        return "low"
