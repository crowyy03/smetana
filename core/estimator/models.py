"""Результат оценки одной позиции."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class EstimationResult:
    item_index: int
    name: str
    description: str
    quantity: Decimal
    unit: str
    unit_price: Decimal
    total_price: Decimal
    section: int
    confidence: float
    reference_ids: list[int] = field(default_factory=list)
    reasoning: str = ""
    needs_manual_review: bool = False
    estimation_method: str = "needs_manual"
