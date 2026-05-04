"""Свободный текст → позиции через Claude."""

from __future__ import annotations

from decimal import Decimal

from core.llm.client import LLMClient, LLMParseError
from core.parsers.types import ParseResult, ParsedItem


PARSE_PROMPT = """Клиент прислал текстовое описание заказа. Извлеки список позиций.

ТЕКСТ КЛИЕНТА:
{text}

Верни JSON:
{{
  "items": [
    {{
      "original_text": "как было в тексте",
      "suggested_name": "краткое название",
      "suggested_description": "полное описание",
      "quantity": число или null,
      "unit": "шт."
    }}
  ],
  "project_hints": {{
    "object_name": "если упомянуто",
    "client_hints": "если упомянуто"
  }},
  "warnings": []
}}
Только JSON, без markdown."""


class TextParser:
    async def parse(self, text: str) -> ParseResult:
        if not text.strip():
            return ParseResult(items=[], confidence=0.0, needs_manual_review=True, parser_notes=["Пустой текст"])
        client = LLMClient()
        try:
            data = await client.complete_json(
                "Ты извлекаешь позиции из письма клиента.",
                PARSE_PROMPT.format(text=text.strip()[:100_000]),
                max_tokens=16000,
                temperature=0,
            )
        except (LLMParseError, Exception) as e:  # noqa: BLE001
            return ParseResult(items=[], confidence=0.0, needs_manual_review=True, parser_notes=[str(e)])
        hints = data.get("project_hints") or {}
        warns = data.get("warnings") or []
        out: list[ParsedItem] = []
        for row in data.get("items") or []:
            q = row.get("quantity")
            qty = Decimal(str(q)) if q is not None else Decimal("1")
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
        return ParseResult(
            items=out,
            confidence=0.75,
            needs_manual_review=len(out) == 0,
            parser_notes=[str(w) for w in warns],
            project_metadata=hints,
        )
