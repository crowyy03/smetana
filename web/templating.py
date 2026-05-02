"""Глобальная конфигурация Jinja2 для веб-приложения."""

from __future__ import annotations

from pathlib import Path

from fastapi.templating import Jinja2Templates

from web import formatting
from web.auth import THEME_COOKIE_NAME

TEMPLATES_DIR = Path(__file__).parent / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# регистрируем фильтры
templates.env.filters["money"] = formatting.format_money
templates.env.filters["money_compact"] = formatting.format_amount_compact
templates.env.filters["qty"] = formatting.format_qty
templates.env.filters["date_short"] = formatting.format_date_short
templates.env.filters["date_full"] = formatting.format_date_full
templates.env.filters["relative"] = formatting.format_relative
templates.env.filters["status_label"] = formatting.status_label
templates.env.filters["method_label"] = formatting.method_label
templates.env.filters["pluralize_ru"] = formatting.pluralize_ru


def _get_theme(request) -> str:
    val = request.cookies.get(THEME_COOKIE_NAME)
    if val in ("day", "night", "system"):
        return val
    return "system"


def _get_user(request):
    return getattr(request.state, "current_user", None)


# глобальные переменные шаблонов
templates.env.globals["initial_theme"] = _get_theme
templates.env.globals["current_user"] = _get_user
templates.env.globals["confidence_marker"] = formatting.confidence_marker
