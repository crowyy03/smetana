"""Парсинг PDF через pdfplumber."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from pathlib import Path
from typing import Any

import pdfplumber

from core.llm.client import LLMClient, LLMParseError
from core.parsers.types import ParseResult, ParsedItem


class PDFParser:
    def _extract_sync(self, file_path: Path) -> tuple[str, list[list[Any]]]:
        full_text_parts: list[str] = []
        tables: list[list[Any]] = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text() or ""
                full_text_parts.append(t)
                for tbl in page.extract_tables() or []:
                    if tbl:
                        tables.append(tbl)
        return "\n".join(full_text_parts), tables

    def _tables_to_items(self, tables: list[list[Any]]) -> list[ParsedItem]:
        items: list[ParsedItem] = []
        for tbl in tables:
            if not tbl or len(tbl) < 2:
                continue
            header = [str(c or "").lower() for c in tbl[0]]
            desc_i = qty_i = None
            for j, h in enumerate(header):
                if any(x in h for x in ("описан", "наимен", "позиц", "издел")):
                    desc_i = j
                if any(x in h for x in ("кол", "qty", "к-во")):
                    qty_i = j
            if desc_i is None:
                continue
            for row in tbl[1:]:
                if not row or desc_i >= len(row):
                    continue
                desc = str(row[desc_i] or "").strip()
                if not desc:
                    continue
                qty: Decimal | None = None
                if qty_i is not None and qty_i < len(row) and row[qty_i]:
                    try:
                        s = str(row[qty_i]).replace(" ", "").replace(",", ".")
                        qty = Decimal(s) if s else None
                    except Exception:  # noqa: BLE001
                        qty = None
                if qty is None or qty <= 0:
                    continue
                items.append(
                    ParsedItem(
                        original_text=desc,
                        suggested_name=desc[:120],
                        suggested_description=desc,
                        quantity=qty,
                        unit="шт.",
                        raw_data={},
                    )
                )
        return items

    async def parse_with_claude(self, text: str) -> ParseResult:
        client = LLMClient()
        prompt = f"""Извлеки позиции из текста КП в JSON.
Формат: {{"items": [{{"original_text": "...", "suggested_name": "...", "suggested_description": "...", "quantity": число, "unit": "шт."}}]}}
Только JSON.
ТЕКСТ:
{text[:120_000]}"""
        try:
            data = await client.complete_json(
                "Ты извлекаешь строки коммерческого предложения.",
                prompt,
                max_tokens=6000,
                temperature=0,
            )
        except (LLMParseError, Exception) as e:  # noqa: BLE001
            return ParseResult(items=[], confidence=0.0, needs_manual_review=True, parser_notes=[str(e)])
        out: list[ParsedItem] = []
        for row in data.get("items") or []:
            q = row.get("quantity")
            qty = Decimal(str(q)) if q is not None else None
            out.append(
                ParsedItem(
                    original_text=str(row.get("original_text", "")),
                    suggested_name=str(row.get("suggested_name", "")),
                    suggested_description=str(row.get("suggested_description", "")),
                    quantity=qty,
                    unit=str(row.get("unit") or "шт."),
                    raw_data={},
                )
            )
        return ParseResult(items=out, confidence=0.65, needs_manual_review=len(out) == 0, parser_notes=[])

    async def parse(self, file_path: Path) -> ParseResult:
        text, tables = await asyncio.to_thread(self._extract_sync, file_path)
        items = self._tables_to_items(tables)
        if items:
            return ParseResult(items=items, confidence=0.85, needs_manual_review=False, parser_notes=[])
        return await self.parse_with_claude(text)
