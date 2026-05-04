"""Парсинг PDF через pdfplumber."""

from __future__ import annotations

import asyncio
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pdfplumber

from core.llm.client import LLMClient, LLMParseError
from core.parsers.excel_parser import _parse_qty_with_unit
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

    def _tables_to_items(self, tables: list[list[Any]]) -> tuple[list[ParsedItem], int]:
        items: list[ParsedItem] = []
        non_empty = 0
        for tbl in tables:
            if not tbl or len(tbl) < 2:
                continue
            header = [str(c or "").lower() for c in tbl[0]]
            desc_i = qty_i = unit_i = None
            for j, h in enumerate(header):
                if desc_i is None and any(x in h for x in ("описан", "наимен", "позиц", "издел", "товар")):
                    desc_i = j
                if qty_i is None and (
                    h.startswith(("количеств", "кол-во", "кол.", "к-во", "qty", "объем", "объём"))
                ):
                    if not any(d in h for d in ("вариант", "дн", "часов", "людей")):
                        qty_i = j
                if unit_i is None and any(x in h for x in ("ед.изм", "ед. изм", "единиц", "ед.")):
                    unit_i = j
            if desc_i is None:
                continue
            for row in tbl[1:]:
                if not row or desc_i >= len(row):
                    continue
                desc = str(row[desc_i] or "").strip()
                if not desc:
                    continue
                non_empty += 1
                qty: Decimal | None = None
                unit: str | None = None
                if qty_i is not None and qty_i < len(row):
                    qty, unit = _parse_qty_with_unit(row[qty_i])
                if unit_i is not None and unit_i < len(row):
                    u = row[unit_i]
                    if u is not None and str(u).strip():
                        unit = str(u).strip()
                if qty is None or qty <= 0:
                    for j, c in enumerate(row):
                        if j == desc_i or c is None:
                            continue
                        q2, u2 = _parse_qty_with_unit(c)
                        if q2 is not None and q2 > 0:
                            qty = q2
                            if unit is None:
                                unit = u2
                            break
                if qty is None or qty <= 0:
                    continue
                items.append(
                    ParsedItem(
                        original_text=desc,
                        suggested_name=desc[:120],
                        suggested_description=desc,
                        quantity=qty,
                        unit=(unit or "шт."),
                        raw_data={},
                    )
                )
        return items, non_empty

    async def parse_with_claude(self, text: str) -> ParseResult:
        client = LLMClient()
        prompt = f"""Извлеки ВСЕ позиции из текста КП/спецификации в JSON.
Если количество указано как «27.34 м» / «3 изделия» — извлекай и число, и единицу.
Если qty не указано — поставь 1.

Формат: {{"items": [{{"original_text": "...", "suggested_name": "...", "suggested_description": "...", "quantity": число, "unit": "шт."}}]}}
Только JSON, без markdown.

ТЕКСТ:
{text[:120_000]}"""
        try:
            data = await client.complete_json(
                "Ты извлекаешь строки коммерческого предложения.",
                prompt,
                max_tokens=16000,
                temperature=0,
            )
        except (LLMParseError, Exception) as e:  # noqa: BLE001
            return ParseResult(items=[], confidence=0.0, needs_manual_review=True, parser_notes=[str(e)])
        out: list[ParsedItem] = []
        for row in data.get("items") or []:
            q = row.get("quantity")
            try:
                qty = Decimal(str(q)) if q is not None else None
            except InvalidOperation:
                qty = None
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
        items, non_empty = self._tables_to_items(tables)
        # Уверенный structured: нашли ≥70% строк или таблиц вообще не было, но строк много
        if items and (non_empty == 0 or len(items) / max(non_empty, 1) >= 0.7):
            return ParseResult(items=items, confidence=0.85, needs_manual_review=False, parser_notes=[])
        llm_result = await self.parse_with_claude(text)
        if llm_result.items:
            return llm_result
        if items:
            return ParseResult(
                items=items,
                confidence=0.5,
                needs_manual_review=True,
                parser_notes=["Структурный парсер уверен слабо; LLM не дал результата."],
            )
        return llm_result
