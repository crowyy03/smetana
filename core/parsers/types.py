"""Унифицированные типы после парсинга."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any


@dataclass
class ParsedItem:
    original_text: str
    suggested_name: str
    suggested_description: str
    quantity: Decimal | None
    unit: str | None
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParseSource:
    """Источник: файл и/или текст."""

    file_path: Path | None = None
    text: str | None = None
    file_format: str = "auto"  # xlsx, pdf, docx, text, auto


@dataclass
class ParseResult:
    items: list[ParsedItem]
    confidence: float
    needs_manual_review: bool
    parser_notes: list[str] = field(default_factory=list)
    project_metadata: dict[str, Any] = field(default_factory=dict)
