"""Форматирование сумм для Telegram."""

from decimal import Decimal


def fmt_money(d: Decimal | float | str) -> str:
    v = d if isinstance(d, Decimal) else Decimal(str(d))
    s = f"{v.quantize(Decimal('0.01')):,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", " ") + " ₽"
