"""Генерация PDF через WeasyPrint + Jinja2."""

from __future__ import annotations

import asyncio
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import jinja2
from loguru import logger
from num2words import num2words
from weasyprint import HTML

from config import config
from db.models import Invoice, InvoiceItem


class PDFGenerator:
    def __init__(self) -> None:
        self.template_dir = Path(__file__).resolve().parent / "templates"
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self.template_dir)),
            autoescape=True,
        )
        self.env.filters["money"] = self._format_money
        self.env.filters["rubles"] = self._to_words

    def _format_money(self, value: Decimal | float | str) -> str:
        d = value if isinstance(value, Decimal) else Decimal(str(value))
        s = f"{d:,.2f}".replace(",", "X").replace(".", ",").replace("X", " ")
        return f"{s} ₽"

    def _to_words(self, value: Decimal | float | str) -> str:
        d = value if isinstance(value, Decimal) else Decimal(str(value))
        rub = int(d)
        kop = int((d * 100) % 100)
        try:
            words = num2words(rub, lang="ru")
        except Exception:  # noqa: BLE001
            words = str(rub)
        return f"{words.capitalize()} рублей {kop:02d} копеек"

    def _sync_generate(
        self,
        invoice: Invoice,
        section1_items: list[InvoiceItem],
        section2_items: list[InvoiceItem],
        logo_path: Path,
    ) -> bytes:
        tpl = self.env.get_template("invoice.html")
        now = datetime.now()
        months = (
            "января",
            "февраля",
            "марта",
            "апреля",
            "мая",
            "июня",
            "июля",
            "августа",
            "сентября",
            "октября",
            "ноября",
            "декабря",
        )
        date_str = f"{now.day} {months[now.month - 1]} {now.year} г."

        logo_str = str(logo_path.resolve()) if logo_path.is_file() else ""
        ctx: dict[str, Any] = {
            "logo_path": logo_str,
            "invoice_number": invoice.invoice_number,
            "date": date_str,
            "client_name": invoice.client_name or "—",
            "object_name": invoice.object_name or "—",
            "contact_name": invoice.contact_name or "—",
            "company_name": config.COMPANY_NAME,
            "company_phone": config.COMPANY_PHONE,
            "company_web": config.COMPANY_WEB,
            "company_inn": config.COMPANY_INN,
            "company_kpp": config.COMPANY_KPP,
            "company_address": config.COMPANY_ADDRESS or "—",
            "executor_line": f"{config.EXECUTOR_NAME} {config.EXECUTOR_PHONE}",
            "section1_items": section1_items,
            "section2_items": section2_items,
            "section1_total": self._format_money(invoice.total_section1),
            "section2_total": self._format_money(invoice.total_section2),
            "grand_total": self._format_money(invoice.total_amount),
            "grand_total_words": self._to_words(invoice.total_amount),
        }
        html_str = tpl.render(**ctx)
        base_url = str(self.template_dir.resolve()) + "/"
        doc = HTML(string=html_str, base_url=base_url)
        return doc.write_pdf()

    async def generate(
        self,
        invoice: Invoice,
        items: list[InvoiceItem],
        logo_path: Path | None = None,
    ) -> bytes:
        root = Path(__file__).resolve().parents[2]
        logo = logo_path or (root / "static" / "logo.png")
        if not logo.is_file():
            logger.warning("Logo not found at {}, PDF без изображения логотипа", logo)
        section1 = [i for i in items if i.section == 1]
        section2 = [i for i in items if i.section == 2]
        return await asyncio.to_thread(
            self._sync_generate,
            invoice,
            section1,
            section2,
            logo,
        )
