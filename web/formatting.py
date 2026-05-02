"""Форматирование чисел и дат для шаблонов."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

NBSP = " "  # NARROW NO-BREAK SPACE


_RU_MONTHS_SHORT = (
    "янв", "фев", "мар", "апр", "май", "июн",
    "июл", "авг", "сен", "окт", "ноя", "дек",
)
_RU_MONTHS_FULL = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)


def format_money(value: Decimal | float | int | str | None, *, with_sign: bool = True) -> str:
    if value is None or value == "":
        return "—"
    d = value if isinstance(value, Decimal) else Decimal(str(value))
    rounded = d.quantize(Decimal("0.01"))
    int_part, _, frac_part = f"{rounded:.2f}".partition(".")
    sign = ""
    if int_part.startswith("-"):
        sign = "−"
        int_part = int_part[1:]
    digits = int_part[::-1]
    grouped = NBSP.join(digits[i:i + 3] for i in range(0, len(digits), 3))[::-1]
    body = f"{sign}{grouped}"
    if rounded != rounded.to_integral_value():
        body = f"{body},{frac_part}"
    return f"{body}{NBSP}₽" if with_sign else body


def format_amount_compact(value: Decimal | float | int | str | None) -> str:
    """Без копеек, для итогов в дашборде."""
    if value is None or value == "":
        return "—"
    d = value if isinstance(value, Decimal) else Decimal(str(value))
    rounded = d.quantize(Decimal("1"))
    s = str(rounded)
    sign = ""
    if s.startswith("-"):
        sign = "−"; s = s[1:]
    digits = s[::-1]
    grouped = NBSP.join(digits[i:i + 3] for i in range(0, len(digits), 3))[::-1]
    return f"{sign}{grouped}{NBSP}₽"


def format_qty(value: Decimal | float | int | str | None) -> str:
    if value is None or value == "":
        return "—"
    d = value if isinstance(value, Decimal) else Decimal(str(value))
    if d == d.to_integral_value():
        return str(int(d))
    return str(d.normalize())


def format_date_short(d: date | datetime | None) -> str:
    if d is None:
        return "—"
    if isinstance(d, datetime):
        d = d.date()
    return f"{d.day} {_RU_MONTHS_SHORT[d.month - 1]} {d.year}"


def format_date_full(d: date | datetime | None) -> str:
    if d is None:
        return "—"
    if isinstance(d, datetime):
        d = d.date()
    return f"{d.day} {_RU_MONTHS_FULL[d.month - 1]} {d.year}"


def format_relative(d: datetime | None) -> str:
    if d is None:
        return "—"
    from datetime import timezone
    now = datetime.now(timezone.utc)
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    delta = now - d
    secs = int(delta.total_seconds())
    if secs < 60: return "только что"
    if secs < 3600: return f"{secs // 60} мин. назад"
    if secs < 86400: return f"{secs // 3600} ч. назад"
    if secs < 86400 * 7: return f"{secs // 86400} дн. назад"
    return format_date_short(d)


_INVOICE_STATUS_RU = {
    "draft": "черновик",
    "estimating": "в работе",
    "generated": "готова",
    "cancelled": "отменена",
}


def status_label(s: str | None) -> str:
    return _INVOICE_STATUS_RU.get((s or "").lower(), s or "—")


_METHOD_LABELS = {
    "auto_high": "auto",
    "auto_medium": "проверка",
    "needs_manual": "вручную",
    "manual": "вручную",
}


def method_label(m: str | None) -> str:
    return _METHOD_LABELS.get((m or "").lower(), m or "—")


def confidence_marker(conf: float, method: str) -> str:
    """В UI: '· ·' для medium, '' для high, '' для manual (текст вместо)."""
    if method == "manual" or method == "needs_manual":
        return ""
    if conf >= 0.85:
        return ""
    if conf >= 0.6:
        return "··"
    return ""


def safe_int(v) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def pluralize_ru(n: int | None, one: str, few: str, many: str) -> str:
    """Русское склонение по числу: 1/21 → one, 2-4/22-24 → few, иначе → many."""
    if n is None:
        return many
    n = abs(int(n))
    mod10 = n % 10
    mod100 = n % 100
    if mod10 == 1 and mod100 != 11:
        return one
    if 2 <= mod10 <= 4 and not (12 <= mod100 <= 14):
        return few
    return many
