"""Текст для эмбеддингов и поиска."""

from __future__ import annotations

from typing import Any


def build_search_text_from_row(row: dict[str, Any]) -> str:
    parts = [
        str(row.get("name", "")),
        str(row.get("description", "")),
        str(row.get("material") or ""),
        str(row.get("coating") or ""),
        str(row.get("size_text") or ""),
        str(row.get("mounting") or ""),
        str(row.get("category", "")),
    ]
    return " ".join(p for p in parts if p).strip().lower()


def build_search_text_from_invoice_item(name: str, description: str) -> str:
    return f"{name} {description}".strip().lower()
