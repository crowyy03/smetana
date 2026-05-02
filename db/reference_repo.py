"""CRUD для прецедентов (ReferenceProject / ReferenceItem)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Sequence


def _to_dec(v: Any, default: Decimal = Decimal("0")) -> Decimal:
    if v is None or v == "":
        return default
    if isinstance(v, Decimal):
        return v
    try:
        return Decimal(str(v).replace(" ", "").replace(",", "."))
    except (InvalidOperation, ValueError):
        return default

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import Invoice, InvoiceItem, ReferenceItem, ReferenceProject


async def get_project_by_content_hash(session: AsyncSession, content_hash: str) -> ReferenceProject | None:
    r = await session.execute(select(ReferenceProject).where(ReferenceProject.content_hash == content_hash))
    return r.scalar_one_or_none()


async def get_reference_items_active(session: AsyncSession) -> list[ReferenceItem]:
    r = await session.execute(
        select(ReferenceItem)
        .join(ReferenceProject)
        .where(ReferenceProject.is_active.is_(True))
        .order_by(ReferenceItem.id)
    )
    return list(r.scalars().all())


async def get_reference_items_by_ids(session: AsyncSession, ids: Sequence[int]) -> list[ReferenceItem]:
    if not ids:
        return []
    id_list = list(ids)
    r = await session.execute(
        select(ReferenceItem)
        .where(ReferenceItem.id.in_(id_list))
        .options(selectinload(ReferenceItem.project))
    )
    by_id = {x.id: x for x in r.scalars().all()}
    return [by_id[i] for i in id_list if i in by_id]


async def create_reference_project_with_items(
    session: AsyncSession,
    *,
    source_file: str,
    content_hash: str,
    project_name: str,
    client_name: str | None,
    object_type: str,
    project_date: date,
    total_amount: Decimal,
    raw_content: str,
    items_data: list[dict[str, Any]],
    embeddings: list[bytes | None] | None = None,
) -> ReferenceProject:
    """items_data — словари полей ReferenceItem (без project_id). embeddings — параллельный список."""
    proj = ReferenceProject(
        source_file=source_file,
        content_hash=content_hash,
        project_name=project_name,
        client_name=client_name,
        object_type=object_type,
        project_date=project_date,
        total_amount=total_amount,
        items_count=len(items_data),
        raw_content=raw_content,
        is_active=True,
    )
    session.add(proj)
    await session.flush()

    embs = embeddings if embeddings is not None else [None] * len(items_data)
    for row, emb in zip(items_data, embs, strict=True):
        qty = _to_dec(row.get("quantity"), default=Decimal("1"))
        up = _to_dec(row.get("unit_price"), default=Decimal("0"))
        tp_raw = row.get("total_price")
        tp = _to_dec(tp_raw, default=up * qty) if tp_raw not in (None, "") else up * qty
        it = ReferenceItem(
            project_id=proj.id,
            name=str(row.get("name", "")),
            description=str(row.get("description", "")),
            material=row.get("material"),
            coating=row.get("coating"),
            size_text=row.get("size_text"),
            mounting=row.get("mounting"),
            category=str(row.get("category", "other")),
            quantity=qty,
            unit=str(row.get("unit", "шт.")),
            unit_price=up,
            total_price=tp,
            section=int(row.get("section", 1)),
            search_text=str(row.get("search_text", "")),
            embedding=emb,
        )
        session.add(it)
    await session.commit()
    await session.refresh(proj)
    return proj


async def import_from_invoice(session: AsyncSession, invoice_id: int) -> ReferenceProject | None:
    """
    После финализации: добавить подтверждённые позиции сметы как новый ReferenceProject + ReferenceItem.
    """
    inv = await session.get(Invoice, invoice_id)
    if not inv:
        return None
    await session.refresh(inv, attribute_names=["items"])
    items = [i for i in inv.items if i.was_confirmed]
    if not items:
        return None

    raw_lines = "\n".join(f"{i.name} | {i.description} | {i.quantity} {i.unit} | {i.unit_price}" for i in items)
    import hashlib

    h = hashlib.sha256(f"invoice:{inv.id}:{raw_lines}".encode("utf-8")).hexdigest()
    existing = await get_project_by_content_hash(session, h)
    if existing:
        return existing

    total = sum((i.total_price for i in items), start=Decimal("0"))
    ca = inv.completed_at or inv.created_at
    proj_date = ca.date() if hasattr(ca, "date") else date.today()

    rows: list[dict[str, Any]] = []
    for it in items:
        rows.append(
            {
                "name": it.name,
                "description": it.description,
                "material": None,
                "coating": None,
                "size_text": None,
                "mounting": None,
                "category": _guess_category(it.name, it.description),
                "quantity": it.quantity,
                "unit": it.unit,
                "unit_price": it.unit_price,
                "total_price": it.total_price,
                "section": it.section,
                "search_text": f"{it.name} {it.description}".lower(),
            }
        )

    emb_bytes: list[bytes] | None = None
    if rows:
        from core.llm.embeddings_client import EmbeddingsClient

        ec = EmbeddingsClient()
        texts = [str(r["search_text"])[:8000] for r in rows]
        vecs = await ec.create_batch(texts)
        emb_bytes = [v.tobytes() for v in vecs]

    return await create_reference_project_with_items(
        session,
        source_file=f"invoice_{inv.id}_{inv.invoice_number}",
        content_hash=h,
        project_name=inv.object_name or f"Проект #{inv.id}",
        client_name=inv.client_name,
        object_type=inv.object_type or "other",
        project_date=proj_date if isinstance(proj_date, date) else date.today(),
        total_amount=total,
        raw_content=raw_lines[:500_000],
        items_data=rows,
        embeddings=emb_bytes,
    )


def _guess_category(name: str, description: str) -> str:
    t = f"{name} {description}".lower()
    if any(x in t for x in ("доставк", "упаковк", "монтаж", "такелаж")):
        return "service"
    if "портал" in t or "двер" in t:
        return "door_portal"
    if "стойк" in t or "ресепшн" in t or "барн" in t:
        return "stand"
    if "панел" in t or "декор" in t:
        return "panel"
    if any(x in t for x in ("навигац", "номер", "этаж", "квартир", "табличк", "пиктограм")):
        return "navigation"
    return "other"


async def delete_project_by_hash(session: AsyncSession, content_hash: str) -> None:
    proj = await get_project_by_content_hash(session, content_hash)
    if proj:
        await session.execute(delete(ReferenceItem).where(ReferenceItem.project_id == proj.id))
        await session.delete(proj)
        await session.commit()
