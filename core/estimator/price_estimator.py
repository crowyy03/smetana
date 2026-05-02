"""Батч-оценка цен через прецеденты + Claude."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from config import config
from core.estimator.confidence import classify_method
from core.estimator.models import EstimationResult
from core.estimator.prompts import ESTIMATION_SYSTEM_PROMPT, ESTIMATION_USER_PROMPT
from core.llm.client import LLMClient, LLMParseError
from core.parsers.types import ParsedItem
from core.reference_db.retriever import ReferenceRetriever


class PriceEstimator:
    def __init__(self) -> None:
        self.llm = LLMClient()
        self.retriever = ReferenceRetriever()

    async def estimate_batch(
        self,
        session: AsyncSession,
        new_items: list[ParsedItem],
        project_context: str = "",
        progress_cb=None,
    ) -> list[EstimationResult]:
        if not new_items:
            return []

        async def _emit(stage: str, current: int = 0, total: int = 0, label: str = "") -> None:
            if progress_cb is None:
                return
            try:
                await progress_cb(stage=stage, current=current, total=total, label=label)
            except Exception:  # noqa: BLE001
                logger.debug("progress_cb failed (ignoring)")

        await _emit("loading_index")
        await self.retriever.load_index(session)

        items_with_refs: list[tuple[int, ParsedItem, list[tuple[Any, float]]]] = []
        total_n = len(new_items)
        for idx, item in enumerate(new_items):
            await _emit("finding_refs", current=idx + 1, total=total_n, label=item.suggested_name or item.original_text[:80])
            q = f"{item.suggested_name} {item.suggested_description}".strip()
            refs = await self.retriever.find_similar(session, q, top_k=config.TOP_K_REFERENCES)
            items_with_refs.append((idx, item, refs))

        refs_payload: list[dict[str, Any]] = []
        seen: set[int] = set()
        for _, _, refs in items_with_refs:
            for ref, score in refs:
                if ref.id in seen:
                    continue
                seen.add(ref.id)
                refs_payload.append(
                    {
                        "id": ref.id,
                        "similarity": round(score, 4),
                        "project": ref.project.project_name if ref.project else "",
                        "name": ref.name,
                        "description": ref.description[:500],
                        "material": ref.material,
                        "coating": ref.coating,
                        "size_text": ref.size_text,
                        "mounting": ref.mounting,
                        "unit": ref.unit,
                        "unit_price": float(ref.unit_price),
                        "total_price": float(ref.total_price),
                        "quantity": float(ref.quantity),
                        "section": ref.section,
                        "category": ref.category,
                    }
                )

        new_json = [
            {
                "item_index": i,
                "original": it.original_text,
                "name": it.suggested_name,
                "description": it.suggested_description,
                "quantity": float(it.quantity) if it.quantity is not None else None,
                "unit": it.unit or "шт.",
            }
            for i, it in enumerate(new_items)
        ]

        user = ESTIMATION_USER_PROMPT.format(
            project_context=project_context or "(не указан)",
            new_items_json=json.dumps(new_json, ensure_ascii=False),
            references_json=json.dumps(refs_payload, ensure_ascii=False),
        )

        if not config.ANTHROPIC_API_KEY:
            return self.fallback_manual(new_items)

        await _emit("llm", total=total_n)
        try:
            data = await self.llm.complete_json(
                ESTIMATION_SYSTEM_PROMPT,
                user,
                max_tokens=8192,
                temperature=0,
            )
        except (LLMParseError, Exception) as e:  # noqa: BLE001
            logger.error("estimate_batch LLM failed: {}", e)
            return self.fallback_manual(new_items)

        out: list[EstimationResult] = []
        for row in data.get("estimations") or []:
            idx = int(row.get("item_index", 0))
            if idx < 0 or idx >= len(new_items):
                continue
            qty = Decimal(str(row.get("quantity", new_items[idx].quantity or 1)))
            up = Decimal(str(row.get("unit_price", 0)))
            sec = int(row.get("section", 1))
            conf = float(row.get("confidence", 0))
            refs_ids = [int(x) for x in row.get("based_on_references") or []]
            nmr = bool(row.get("needs_manual_review", conf < config.MEDIUM_CONFIDENCE_THRESHOLD))
            em = classify_method(conf, nmr)
            tot = up * qty
            out.append(
                EstimationResult(
                    item_index=idx,
                    name=str(row.get("name", "")),
                    description=str(row.get("description", "")),
                    quantity=qty,
                    unit=str(row.get("unit", "шт.")),
                    unit_price=up,
                    total_price=tot,
                    section=sec,
                    confidence=conf,
                    reference_ids=refs_ids,
                    reasoning=str(row.get("reasoning", "")),
                    needs_manual_review=nmr,
                    estimation_method=em,
                )
            )
        out.sort(key=lambda x: x.item_index)
        return out

    @staticmethod
    def fallback_manual(new_items: list[ParsedItem]) -> list[EstimationResult]:
        """Все позиции в ручную оценку (нет LLM или ошибка)."""
        return [
            EstimationResult(
                item_index=i,
                name=it.suggested_name,
                description=it.suggested_description,
                quantity=it.quantity or Decimal("1"),
                unit=it.unit or "шт.",
                unit_price=Decimal("0"),
                total_price=Decimal("0"),
                section=1,
                confidence=0.0,
                reference_ids=[],
                reasoning="LLM недоступен — ручная оценка",
                needs_manual_review=True,
                estimation_method="needs_manual",
            )
            for i, it in enumerate(new_items)
        ]
