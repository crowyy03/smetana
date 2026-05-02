"""Парсинг Excel: структурированный лист или весь текст → Claude."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from core.llm.client import LLMClient, LLMParseError
from core.parsers.types import ParseResult, ParsedItem

KNOWN_SHEET_NAMES = ["КП Форм", "КП форм", "кп форм", "Спецификация", "Смета", "Form", "Sheet"]
QTY_HEADERS = ("количество", "кол-во", "кол.", "к-во", "qty")
DESC_HEADERS = ("описание", "наименование", "позиция", "изделие", "товар")


class ExcelParser:
    def _find_sheet(self, wb: Any) -> Any | None:
        for name in wb.sheetnames:
            for k in KNOWN_SHEET_NAMES:
                if k.lower() in name.lower():
                    return wb[name]
        return wb.active

    def _extract_all_text(self, wb: Any) -> str:
        parts: list[str] = []
        for name in wb.sheetnames:
            ws = wb[name]
            parts.append(f"## Лист: {name}")
            for row in ws.iter_rows(values_only=True):
                line = " | ".join("" if c is None else str(c).strip() for c in row)
                if line.strip():
                    parts.append(line)
        return "\n".join(parts)

    def _is_total(self, s: str) -> bool:
        t = s.lower()
        return any(x in t for x in ("∑", "итого", "total"))

    def _parse_structured(self, ws: Any) -> list[ParsedItem]:
        col_desc = col_qty = None
        max_scan = min(ws.max_row or 200, 200)
        header_row = None
        for ri, row in enumerate(ws.iter_rows(min_row=1, max_row=max_scan, values_only=True), start=1):
            if not row:
                continue
            cells = [str(c).strip().lower() if c is not None else "" for c in row]
            for j, cell in enumerate(cells):
                for d in DESC_HEADERS:
                    if d in cell:
                        col_desc = j
                        break
                for q in QTY_HEADERS:
                    if q in cell:
                        col_qty = j
                        break
            if col_desc is not None and col_qty is not None:
                header_row = ri
                break
        if header_row is None or col_desc is None or col_qty is None:
            return []

        items: list[ParsedItem] = []
        for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
            if not row:
                continue
            desc = row[col_desc] if col_desc < len(row) else None
            qty_cell = row[col_qty] if col_qty < len(row) else None
            desc_s = str(desc).strip() if desc is not None else ""
            if not desc_s or self._is_total(desc_s + str(qty_cell or "")):
                continue
            qty: Decimal | None = None
            if qty_cell is not None:
                try:
                    if isinstance(qty_cell, (int, float)):
                        q = Decimal(str(int(qty_cell)))
                    else:
                        s = str(qty_cell).replace(" ", "").replace(",", ".")
                        if s and s.replace(".", "", 1).replace("-", "", 1).isdigit():
                            q = Decimal(s)
                        else:
                            q = Decimal("0")
                    qty = q if q > 0 else None
                except Exception:  # noqa: BLE001
                    qty = None
            if qty is None:
                continue
            unit = "шт."
            items.append(
                ParsedItem(
                    original_text=desc_s,
                    suggested_name=desc_s[:120],
                    suggested_description=desc_s,
                    quantity=qty,
                    unit=unit,
                    raw_data={"sheet": ws.title},
                )
            )
        return items

    def parse_sync(self, file_path: Path) -> tuple[list[ParsedItem], str, float]:
        wb = load_workbook(file_path, read_only=True, data_only=True)
        try:
            ws = self._find_sheet(wb)
            items = self._parse_structured(ws)
            raw = self._extract_all_text(wb)
            if items:
                return items, raw, 0.95
            return [], raw, 0.3
        finally:
            wb.close()

    async def parse_with_claude(self, raw_text: str) -> ParseResult:
        client = LLMClient()
        prompt = f"""Извлеки позиции из текста Excel в JSON.
Формат: {{"items": [{{"original_text": "...", "suggested_name": "...", "suggested_description": "...", "quantity": число или null, "unit": "шт."}}]}}
Только JSON без markdown.
ТЕКСТ:
{raw_text[:100_000]}"""
        try:
            data = await client.complete_json(
                "Ты извлекаешь строки спецификации.",
                prompt,
                max_tokens=4096,
                temperature=0,
            )
        except (LLMParseError, Exception) as e:  # noqa: BLE001
            return ParseResult(
                items=[],
                confidence=0.0,
                needs_manual_review=True,
                parser_notes=[str(e)],
            )
        out: list[ParsedItem] = []
        for row in data.get("items") or []:
            q = row.get("quantity")
            qty = Decimal(str(q)) if q is not None else None
            out.append(
                ParsedItem(
                    original_text=str(row.get("original_text", "")),
                    suggested_name=str(row.get("suggested_name", row.get("original_text", ""))),
                    suggested_description=str(row.get("suggested_description", "")),
                    quantity=qty,
                    unit=str(row.get("unit") or "шт."),
                    raw_data={},
                )
            )
        return ParseResult(items=out, confidence=0.7, needs_manual_review=len(out) == 0, parser_notes=[])

    async def parse(self, file_path: Path) -> ParseResult:
        items, raw, conf = await asyncio.to_thread(self.parse_sync, file_path)
        if items:
            return ParseResult(
                items=items,
                confidence=conf,
                needs_manual_review=False,
                parser_notes=[],
                project_metadata={},
            )
        return await self.parse_with_claude(raw)
