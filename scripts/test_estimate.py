#!/usr/bin/env python3
"""Тестовый прогон: текст клиента → парсинг → оценка → распечатка карточек.

Запуск:
    python scripts/test_estimate.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.database import AsyncSessionLocal, init_db  # noqa: E402
from db.reference_repo import get_reference_items_by_ids  # noqa: E402
from core.parsers.text_parser import TextParser  # noqa: E402
from core.estimator.price_estimator import PriceEstimator  # noqa: E402


TEST_REQUEST = """Здравствуйте!

Запрашиваем КП на навигацию ЖК "Аметист" (бизнес-класс, 18 этажей, 4 секции):

1. Номера этажей с подсветкой LED 12V — 18 шт., размер 280×280 мм,
   нержавеющая сталь AISI 304 толщина 1мм с покрытием нитрид титана brown,
   монтаж на дистанционных стойках 25 мм от стены.

2. Номера квартир — 196 шт., размер 150×220 мм,
   нержавейка AISI 430 1мм с антипальчиковым покрытием,
   цвет под бронзу KIBO 230304, крепление на клее.

3. Указатели направлений в МОПе (3 типа: лифт, лестница, мусоропровод) —
   24 шт. суммарно, 400×120 мм, нержавейка под бронзу.

4. Дверной портал главного входа — 2 компл., размер 2200×3000 мм,
   нержавейка с зеркальной полировкой mirror champagne gold.

5. Декоративные панели лобби — 28 м², крупноформатные с подсистемой hook-on,
   нержавейка под бронзу KIBO 230302.

6. Стойка ресепшн — 1 компл., габариты 3500×900×1150 мм,
   металлокаркас + нерж панели под бронзу.

Срок поставки — июль 2026. С уважением, Андрей, +7 916 ***.
"""


def fmt_money(v) -> str:
    d = v if isinstance(v, Decimal) else Decimal(str(v))
    s = f"{d:,.2f}".replace(",", " ").replace(".", ",")
    return f"{s} ₽"


EMOJI = {"auto_high": "🟢", "auto_medium": "🟡", "needs_manual": "🔴"}


async def main(request_text: str | None = None) -> None:
    text = request_text or TEST_REQUEST
    await init_db()
    print("=" * 70)
    print("ТЕСТОВЫЙ ЗАПРОС КЛИЕНТА")
    print("=" * 70)
    print(text)

    parsed = await TextParser().parse(text)
    if not parsed.items:
        print("ОШИБКА: парсер не извлёк позиции")
        for n in parsed.parser_notes:
            print("  ", n)
        return

    print(f"\nПарсер вытащил {len(parsed.items)} позиций. Иду в оценку...\n")

    async with AsyncSessionLocal() as session:
        estimator = PriceEstimator()
        results = await estimator.estimate_batch(session, parsed.items, project_context="ЖК Аметист, бизнес-класс, 18 этажей")

        total = Decimal("0")
        for er in results:
            emoji = EMOJI.get(er.estimation_method, "⚪")
            print("=" * 70)
            print(f"{emoji}  Позиция {er.item_index + 1}: {er.name}")
            print("-" * 70)
            print(f"   Описание: {er.description[:200]}")
            print(f"   Кол-во:    {er.quantity} {er.unit}")
            print(f"   Цена ед.:  {fmt_money(er.unit_price)}")
            print(f"   Итого:     {fmt_money(er.total_price)}")
            print(f"   Confidence: {er.confidence:.2f}  (метод: {er.estimation_method})")
            if er.reasoning:
                print(f"   💡 {er.reasoning}")
            if er.reference_ids:
                refs = await get_reference_items_by_ids(session, er.reference_ids)
                print("   🔍 На основе:")
                for ref in refs[:3]:
                    pname = ref.project.project_name if ref.project else "?"
                    sz = f" [{ref.size_text}]" if ref.size_text else ""
                    print(
                        f"      • {pname} — {ref.name}{sz}: "
                        f"{fmt_money(ref.unit_price)}/{ref.unit}"
                    )
            total += er.total_price

        print("=" * 70)
        print(f"ИТОГО ПО ЗАПРОСУ: {fmt_money(total)}")
        print("=" * 70)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            asyncio.run(main(f.read()))
    else:
        asyncio.run(main())
