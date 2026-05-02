"""CRUD для смет (Invoice / InvoiceItem)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Sequence

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import Invoice, InvoiceItem


async def next_invoice_number(session: AsyncSession) -> str:
    now = datetime.now(timezone.utc)
    yy = now.year % 100
    mm = now.month
    prefix = f"{yy:02d}-{mm:02d}/"
    r = await session.execute(
        select(func.count()).select_from(Invoice).where(Invoice.invoice_number.like(f"{prefix}%"))
    )
    n = int(r.scalar_one() or 0) + 1
    return f"{prefix}{n}"


async def create_draft_invoice(
    session: AsyncSession,
    *,
    telegram_user_id: int | None = None,
    telegram_username: str | None = None,
    user_id: int | None = None,
    source_file_name: str | None,
    source_format: str,
    items_payload: list[dict[str, Any]],
    created_via: str | None = None,
) -> Invoice:
    """items_payload: поля для InvoiceItem + sort_order опционально.

    Должен быть передан хотя бы один из: telegram_user_id (для бота) или user_id (для веба).
    """
    if telegram_user_id is None and user_id is None:
        raise ValueError("Нужен telegram_user_id или user_id")
    via = created_via or ("web" if user_id is not None else "bot")
    num = await next_invoice_number(session)
    inv = Invoice(
        invoice_number=num,
        telegram_user_id=telegram_user_id,
        telegram_username=telegram_username,
        user_id=user_id,
        created_via=via,
        status="estimating",
        source_file_name=source_file_name,
        source_format=source_format,
    )
    session.add(inv)
    await session.flush()
    for i, row in enumerate(items_payload):
        it = InvoiceItem(
            invoice_id=inv.id,
            sort_order=int(row.get("sort_order", i)),
            original_text=str(row.get("original_text", "")),
            name=str(row.get("name", "")),
            description=str(row.get("description", "")),
            quantity=Decimal(str(row.get("quantity", 1))),
            unit=str(row.get("unit", "шт.")),
            unit_price=Decimal(str(row.get("unit_price", 0))),
            total_price=Decimal(str(row.get("total_price", 0))),
            section=int(row.get("section", 1)),
            estimation_method=str(row.get("estimation_method", "needs_manual")),
            confidence=float(row.get("confidence", 0)),
            reference_item_ids=json.dumps(row.get("reference_item_ids", []), ensure_ascii=False),
            estimation_reasoning=str(row.get("estimation_reasoning", "")),
            original_suggested_unit_price=(
                Decimal(str(row["original_suggested_unit_price"]))
                if row.get("original_suggested_unit_price") is not None
                else None
            ),
        )
        session.add(it)
    await _recalc_totals(session, inv.id)
    await session.commit()
    await session.refresh(inv)
    return inv


async def get_invoice_with_items(session: AsyncSession, invoice_id: int) -> Invoice | None:
    r = await session.execute(
        select(Invoice)
        .where(Invoice.id == invoice_id)
        .options(selectinload(Invoice.items))
    )
    inv = r.scalar_one_or_none()
    if inv:
        inv.items.sort(key=lambda x: x.sort_order)
    return inv


async def list_invoice_items(session: AsyncSession, invoice_id: int) -> list[InvoiceItem]:
    inv = await get_invoice_with_items(session, invoice_id)
    return list(inv.items) if inv else []


async def get_invoice_item(session: AsyncSession, item_id: int) -> InvoiceItem | None:
    return await session.get(InvoiceItem, item_id)


async def get_invoice_item_by_sort(session: AsyncSession, invoice_id: int, sort_order: int) -> InvoiceItem | None:
    r = await session.execute(
        select(InvoiceItem).where(InvoiceItem.invoice_id == invoice_id, InvoiceItem.sort_order == sort_order)
    )
    return r.scalar_one_or_none()


async def confirm_item(session: AsyncSession, invoice_id: int, item_id: int) -> None:
    await session.execute(
        update(InvoiceItem)
        .where(InvoiceItem.id == item_id, InvoiceItem.invoice_id == invoice_id)
        .values(was_confirmed=True)
    )
    await session.commit()


async def update_item_price(
    session: AsyncSession,
    invoice_id: int,
    item_id: int,
    new_unit_price: Decimal,
    *,
    was_modified: bool = True,
) -> None:
    it = await session.get(InvoiceItem, item_id)
    if not it or it.invoice_id != invoice_id:
        return
    if it.original_suggested_unit_price is None:
        await session.execute(
            update(InvoiceItem).where(InvoiceItem.id == item_id).values(original_suggested_unit_price=it.unit_price)
        )
    qty = it.quantity
    new_total = new_unit_price * qty
    await session.execute(
        update(InvoiceItem)
        .where(InvoiceItem.id == item_id)
        .values(
            unit_price=new_unit_price,
            total_price=new_total,
            was_modified=was_modified,
            estimation_method="manual" if was_modified else it.estimation_method,
        )
    )
    await _recalc_totals(session, invoice_id)
    await session.commit()


async def update_item_quantity(session: AsyncSession, invoice_id: int, item_id: int, new_qty: Decimal) -> None:
    it = await session.get(InvoiceItem, item_id)
    if not it or it.invoice_id != invoice_id:
        return
    new_total = it.unit_price * new_qty
    await session.execute(
        update(InvoiceItem)
        .where(InvoiceItem.id == item_id)
        .values(quantity=new_qty, total_price=new_total, was_modified=True)
    )
    await _recalc_totals(session, invoice_id)
    await session.commit()


async def delete_item(session: AsyncSession, invoice_id: int, item_id: int) -> None:
    it = await session.get(InvoiceItem, item_id)
    if not it or it.invoice_id != invoice_id:
        return
    await session.delete(it)
    await session.flush()
    await _renumber_sort_orders(session, invoice_id)
    await _recalc_totals(session, invoice_id)
    await session.commit()


async def add_manual_item(
    session: AsyncSession,
    invoice_id: int,
    *,
    name: str,
    description: str,
    quantity: Decimal,
    unit: str,
    unit_price: Decimal,
    section: int = 1,
) -> InvoiceItem:
    items = await list_invoice_items(session, invoice_id)
    next_order = max((i.sort_order for i in items), default=-1) + 1
    total = quantity * unit_price
    it = InvoiceItem(
        invoice_id=invoice_id,
        sort_order=next_order,
        original_text=name,
        name=name,
        description=description,
        quantity=quantity,
        unit=unit,
        unit_price=unit_price,
        total_price=total,
        section=section,
        estimation_method="manual",
        confidence=1.0,
        reference_item_ids="[]",
        estimation_reasoning="Добавлено вручную",
        was_confirmed=False,
        was_modified=True,
    )
    session.add(it)
    await _recalc_totals(session, invoice_id)
    await session.commit()
    await session.refresh(it)
    return it


async def update_invoice_meta(
    session: AsyncSession,
    invoice_id: int,
    **fields: Any,
) -> None:
    allowed = {"client_name", "contact_name", "object_name", "object_type", "status"}
    data = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not data:
        return
    await session.execute(update(Invoice).where(Invoice.id == invoice_id).values(**data))
    await session.commit()


async def mark_invoice_completed(session: AsyncSession, invoice_id: int, pdf_path: str | None = None) -> None:
    await session.execute(
        update(Invoice)
        .where(Invoice.id == invoice_id)
        .values(
            status="generated",
            completed_at=datetime.now(timezone.utc),
            pdf_path=pdf_path,
        )
    )
    await session.commit()


async def all_items_confirmed(session: AsyncSession, invoice_id: int) -> bool:
    items = await list_invoice_items(session, invoice_id)
    return bool(items) and all(i.was_confirmed for i in items)


async def _renumber_sort_orders(session: AsyncSession, invoice_id: int) -> None:
    items = await list_invoice_items(session, invoice_id)
    for i, it in enumerate(sorted(items, key=lambda x: x.sort_order)):
        it.sort_order = i
    await session.flush()


async def _recalc_totals(session: AsyncSession, invoice_id: int) -> None:
    await session.flush()
    items = await list_invoice_items(session, invoice_id)
    s1 = sum((i.total_price for i in items if i.section == 1), start=Decimal("0"))
    s2 = sum((i.total_price for i in items if i.section == 2), start=Decimal("0"))
    tot = s1 + s2
    await session.execute(
        update(Invoice)
        .where(Invoice.id == invoice_id)
        .values(total_section1=s1, total_section2=s2, total_amount=tot)
    )


async def stats_admin(session: AsyncSession) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    q_today = select(func.count()).select_from(Invoice).where(Invoice.created_at >= start_today)
    q_month = select(func.count()).select_from(Invoice).where(Invoice.created_at >= start_month)
    q_sum = (
        select(func.coalesce(func.sum(Invoice.total_amount), 0))
        .select_from(Invoice)
        .where(Invoice.created_at >= start_month)
    )
    today_c = int((await session.execute(q_today)).scalar_one() or 0)
    month_c = int((await session.execute(q_month)).scalar_one() or 0)
    month_sum = (await session.execute(q_sum)).scalar_one()
    return {"invoices_today": today_c, "invoices_month": month_c, "total_month": Decimal(str(month_sum or 0))}


async def list_recent_invoices(session: AsyncSession, limit: int = 10) -> Sequence[Invoice]:
    r = await session.execute(select(Invoice).order_by(Invoice.created_at.desc()).limit(limit))
    return r.scalars().all()


async def list_invoices_paginated(
    session: AsyncSession,
    *,
    page: int = 1,
    per_page: int = 50,
    search: str | None = None,
    user_id: int | None = None,
    status: str | None = None,
) -> tuple[Sequence[Invoice], int]:
    q = select(Invoice).order_by(Invoice.created_at.desc())
    count_q = select(func.count()).select_from(Invoice)
    if search:
        like = f"%{search.strip()}%"
        cond = (
            Invoice.invoice_number.ilike(like)
            | Invoice.client_name.ilike(like)
            | Invoice.object_name.ilike(like)
            | Invoice.contact_name.ilike(like)
        )
        q = q.where(cond)
        count_q = count_q.where(cond)
    if user_id is not None:
        q = q.where(Invoice.user_id == user_id)
        count_q = count_q.where(Invoice.user_id == user_id)
    if status:
        q = q.where(Invoice.status == status)
        count_q = count_q.where(Invoice.status == status)
    q = q.limit(per_page).offset((page - 1) * per_page)
    rows = (await session.execute(q)).scalars().all()
    total = int((await session.execute(count_q)).scalar_one() or 0)
    return rows, total


async def stats_for_user(session: AsyncSession, user_id: int) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    start_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    q_month = select(func.count()).select_from(Invoice).where(
        Invoice.user_id == user_id, Invoice.created_at >= start_month
    )
    q_total = select(func.count()).select_from(Invoice).where(Invoice.user_id == user_id)
    q_review = (
        select(func.count())
        .select_from(Invoice)
        .where(Invoice.user_id == user_id, Invoice.status.in_(("estimating", "draft")))
    )
    return {
        "month": int((await session.execute(q_month)).scalar_one() or 0),
        "total": int((await session.execute(q_total)).scalar_one() or 0),
        "in_progress": int((await session.execute(q_review)).scalar_one() or 0),
    }
