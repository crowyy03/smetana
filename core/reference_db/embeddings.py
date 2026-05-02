"""Текст для эмбеддингов и поиска."""

from __future__ import annotations

from typing import Any

from core.reference_db.synonyms import expand_synonyms


def build_search_text_from_row(row: dict[str, Any]) -> str:
    name = str(row.get("name", ""))
    desc = str(row.get("description", ""))[:300]
    parts = [
        name,
        name,  # умножаем вес продуктового названия
        str(row.get("category", "")),
        str(row.get("size_text") or ""),
        desc,
        str(row.get("material") or "")[:80],
        str(row.get("coating") or "")[:60],
        str(row.get("mounting") or "")[:60],
    ]
    base = " ".join(p for p in parts if p).strip().lower()
    return expand_synonyms(base)


def build_search_text_from_invoice_item(name: str, description: str) -> str:
    base = f"{name} {name} {description}".strip().lower()
    return expand_synonyms(base)
