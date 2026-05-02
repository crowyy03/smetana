"""Маршруты смет: список, создание (upload + SSE), построчное подтверждение, PDF."""

from __future__ import annotations

import asyncio
import json
import uuid
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
)
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from core.estimator.price_estimator import PriceEstimator
from core.parsers.text_parser import TextParser
from core.parsers.types import ParseSource
from core.parsers.universal import UniversalParser
from core.pdf.generator import PDFGenerator
from db import invoice_repo, reference_repo
from db.database import AsyncSessionLocal
from db.models import InvoiceItem, ReferenceItem, User
from web.deps import get_session, require_user
from web.templating import templates

router = APIRouter(prefix="/estimates", tags=["estimates"])

UPLOAD_DIR = Path("data/uploads")
PDF_DIR = Path("data/pdf")

# in-memory job tracker для SSE upload progress.
# job_id → asyncio.Queue[dict]
_jobs: dict[str, asyncio.Queue] = {}
_job_results: dict[str, dict[str, Any]] = {}


def _detect_format(filename: str) -> str:
    n = (filename or "").lower()
    if n.endswith(".xlsx"):
        return "xlsx"
    if n.endswith(".xls"):
        return "xls"
    if n.endswith(".pdf"):
        return "pdf"
    if n.endswith(".docx"):
        return "docx"
    return "text"


# ---------------- LIST ----------------


@router.get("")
async def estimates_list(
    request: Request,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
    page: int = 1,
    q: str | None = None,
    status: str | None = None,
    scope: str = "mine",
):
    user_filter = user.id if scope == "mine" else None
    rows, total = await invoice_repo.list_invoices_paginated(
        session,
        page=max(1, page),
        per_page=50,
        search=q,
        user_id=user_filter,
        status=status,
    )
    has_next = total > page * 50
    has_prev = page > 1
    return templates.TemplateResponse(
        request,
        "estimates/list.html",
        {
            "request": request,
            "user": user,
            "rows": rows,
            "total": total,
            "page": page,
            "q": q or "",
            "status": status or "",
            "scope": scope,
            "has_next": has_next,
            "has_prev": has_prev,
        },
    )


# ---------------- NEW ----------------


@router.get("/new")
async def new_estimate_form(request: Request, user: User = Depends(require_user)):
    return templates.TemplateResponse(
        request,
        "estimates/new.html",
        {"request": request, "user": user},
    )


@router.post("/new", response_class=HTMLResponse)
async def new_estimate_submit(
    request: Request,
    background_tasks: BackgroundTasks,
    user: User = Depends(require_user),
    file: UploadFile | None = File(default=None),
    text: str = Form(default=""),
):
    """Принимает файл или текст. Создаёт фоновую задачу обработки и возвращает страницу прогресса."""
    has_file = file is not None and file.filename
    has_text = bool(text.strip())
    if not has_file and not has_text:
        return templates.TemplateResponse(
            request,
            "estimates/new.html",
            {
                "request": request,
                "user": user,
                "error": "Загрузите файл или вставьте текст запроса.",
            },
            status_code=400,
        )

    job_id = uuid.uuid4().hex
    _jobs[job_id] = asyncio.Queue()

    if has_file:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        ext = Path(file.filename).suffix or ".bin"
        dest = UPLOAD_DIR / f"{job_id}{ext}"
        body = await file.read()
        dest.write_bytes(body)
        background_tasks.add_task(
            _process_file_job, job_id, user.id, dest, file.filename, _detect_format(file.filename)
        )
    else:
        background_tasks.add_task(_process_text_job, job_id, user.id, text)

    return templates.TemplateResponse(
        request,
        "estimates/processing.html",
        {"request": request, "user": user, "job_id": job_id},
    )


@router.get("/process/{job_id}/events")
async def process_events(job_id: str, user: User = Depends(require_user)):
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    q = _jobs[job_id]

    async def gen():
        while True:
            try:
                msg = await asyncio.wait_for(q.get(), timeout=60)
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": "."}
                continue
            yield msg
            if msg.get("event") in ("done", "error"):
                break

    return EventSourceResponse(gen())


async def _emit(job_id: str, event: str, data: Any) -> None:
    q = _jobs.get(job_id)
    if not q:
        return
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    await q.put({"event": event, "data": payload})


def _items_payload(parse_items, results) -> list[dict[str, Any]]:
    if len(results) != len(parse_items):
        results = PriceEstimator.fallback_manual(parse_items)
    payload: list[dict[str, Any]] = []
    for i, (pi, er) in enumerate(zip(parse_items, results, strict=True)):
        payload.append(
            {
                "sort_order": i,
                "original_text": pi.original_text,
                "name": er.name or pi.suggested_name,
                "description": er.description or pi.suggested_description,
                "quantity": er.quantity,
                "unit": er.unit,
                "unit_price": er.unit_price,
                "total_price": er.total_price,
                "section": er.section,
                "estimation_method": er.estimation_method,
                "confidence": er.confidence,
                "reference_item_ids": er.reference_ids,
                "estimation_reasoning": er.reasoning,
                "original_suggested_unit_price": er.unit_price,
            }
        )
    return payload


async def _process_file_job(job_id: str, user_id: int, file_path: Path, original_name: str, fmt: str) -> None:
    try:
        await _emit(job_id, "stage", {"stage": "received", "label": original_name})
        if fmt == "xls":
            await _emit(job_id, "error", "Формат .xls не поддерживается. Конвертируйте в .xlsx.")
            return
        await _emit(job_id, "stage", {"stage": "parsing", "label": f"{fmt.upper()}"})
        parser = UniversalParser()
        try:
            parse_result = await parser.parse(ParseSource(file_path=file_path, file_format=fmt))
        except Exception as e:  # noqa: BLE001
            await _emit(job_id, "error", f"Не смог разобрать файл: {e}")
            return
        if not parse_result.items:
            await _emit(job_id, "error", "В файле не найдено позиций.")
            return
        if parse_result.parser_notes:
            for note in parse_result.parser_notes:
                await _emit(job_id, "log", f"Замечание парсера: {note}")
        await _finalize_job(job_id, user_id, parse_result, source_file_name=original_name, source_format=fmt)
    finally:
        try:
            file_path.unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            pass


async def _process_text_job(job_id: str, user_id: int, text: str) -> None:
    await _emit(job_id, "stage", {"stage": "received", "label": "Текст запроса"})
    await _emit(job_id, "stage", {"stage": "parsing", "label": "TEXT"})
    parse_result = await TextParser().parse(text)
    if not parse_result.items:
        notes = "; ".join(parse_result.parser_notes) if parse_result.parser_notes else "не извлечено позиций"
        await _emit(job_id, "error", f"Не получилось разобрать текст: {notes}")
        return
    await _finalize_job(job_id, user_id, parse_result, source_file_name=None, source_format="text")


async def _finalize_job(job_id: str, user_id: int, parse_result, *, source_file_name: str | None, source_format: str) -> None:
    await _emit(
        job_id, "stage",
        {"stage": "found_items", "current": len(parse_result.items), "total": len(parse_result.items),
         "label": "Позиции собраны"},
    )
    project_ctx = json.dumps(parse_result.project_metadata or {}, ensure_ascii=False)

    async def progress(*, stage: str, current: int = 0, total: int = 0, label: str = "") -> None:
        await _emit(job_id, "stage", {"stage": stage, "current": current, "total": total, "label": label})

    async with AsyncSessionLocal() as session:
        try:
            estimator = PriceEstimator()
            results = await estimator.estimate_batch(
                session, parse_result.items, project_context=project_ctx, progress_cb=progress,
            )
        except Exception as e:  # noqa: BLE001
            logger.exception("estimate failed")
            await _emit(job_id, "log", f"LLM-оценка упала ({e}). Все позиции пойдут на ручную оценку.")
            results = PriceEstimator.fallback_manual(parse_result.items)
        await _emit(job_id, "stage", {"stage": "saving", "label": "Сохраняю смету"})
        payload = _items_payload(parse_result.items, results)
        inv = await invoice_repo.create_draft_invoice(
            session,
            user_id=user_id,
            source_file_name=source_file_name,
            source_format=source_format,
            items_payload=payload,
        )
    await _emit(job_id, "done", {"invoice_id": inv.id})
    _job_results[job_id] = {"invoice_id": inv.id}


# ---------------- DETAIL (line-by-line confirmation) ----------------


@router.get("/{invoice_id}")
async def estimate_detail(
    invoice_id: int,
    request: Request,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    inv = await invoice_repo.get_invoice_with_items(session, invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Смета не найдена")
    refs_map = await _refs_for_items(session, inv.items)
    confirmed = sum(1 for i in inv.items if i.was_confirmed)
    total_count = len(inv.items)
    return templates.TemplateResponse(
        request,
        "estimates/detail.html",
        {
            "request": request,
            "user": user,
            "inv": inv,
            "items": inv.items,
            "refs_map": refs_map,
            "confirmed_count": confirmed,
            "total_count": total_count,
            "progress_pct": int(round((confirmed / total_count) * 100)) if total_count else 0,
        },
    )


async def _refs_for_items(session: AsyncSession, items) -> dict[int, list[ReferenceItem]]:
    """Для каждой позиции сметы вернуть список ReferenceItem по reference_item_ids (с проектом)."""
    all_ids: set[int] = set()
    per_item_ids: dict[int, list[int]] = {}
    for it in items:
        try:
            ids = json.loads(it.reference_item_ids or "[]")
        except (ValueError, TypeError):
            ids = []
        ids = [int(x) for x in ids if isinstance(x, (int, str)) and str(x).isdigit()]
        per_item_ids[it.id] = ids
        all_ids.update(ids)
    if not all_ids:
        return {it.id: [] for it in items}
    refs = await reference_repo.get_reference_items_by_ids(session, sorted(all_ids))
    by_id = {r.id: r for r in refs}
    return {it.id: [by_id[i] for i in per_item_ids[it.id] if i in by_id] for it in items}


# ---------------- HTMX item endpoints ----------------


def _row_context(inv, item: InvoiceItem, refs: list[ReferenceItem]) -> dict[str, Any]:
    return {"inv": inv, "item": item, "refs": refs}


@router.post("/{invoice_id}/items/{item_id}/confirm")
async def confirm_item_route(
    invoice_id: int,
    item_id: int,
    request: Request,
    unit_price: str = Form(...),
    quantity: str = Form(default=""),
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    inv = await invoice_repo.get_invoice_with_items(session, invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Смета не найдена")
    try:
        new_price = Decimal(unit_price.replace(",", ".").replace(" ", "").replace(" ", ""))
    except (InvalidOperation, ValueError):
        raise HTTPException(status_code=400, detail="Неверная цена")
    item = next((i for i in inv.items if i.id == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Позиция не найдена")
    was_modified = new_price != (item.unit_price or Decimal("0"))
    if quantity:
        try:
            new_qty = Decimal(quantity.replace(",", ".").replace(" ", ""))
            if new_qty != item.quantity:
                await invoice_repo.update_item_quantity(session, invoice_id, item_id, new_qty)
        except (InvalidOperation, ValueError):
            pass
    if was_modified:
        await invoice_repo.update_item_price(session, invoice_id, item_id, new_price, was_modified=True)
    await invoice_repo.confirm_item(session, invoice_id, item_id)
    inv = await invoice_repo.get_invoice_with_items(session, invoice_id)
    item = next((i for i in inv.items if i.id == item_id), None)
    refs_map = await _refs_for_items(session, [item])
    return templates.TemplateResponse(
        request,
        "estimates/_row.html",
        {"request": request, "inv": inv, "item": item, "refs": refs_map[item.id]},
    )


@router.post("/{invoice_id}/items/{item_id}/unconfirm")
async def unconfirm_item_route(
    invoice_id: int,
    item_id: int,
    request: Request,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    from sqlalchemy import update
    from db.models import InvoiceItem as IItem

    await session.execute(update(IItem).where(IItem.id == item_id, IItem.invoice_id == invoice_id).values(was_confirmed=False))
    await session.commit()
    inv = await invoice_repo.get_invoice_with_items(session, invoice_id)
    item = next((i for i in inv.items if i.id == item_id), None)
    refs_map = await _refs_for_items(session, [item])
    return templates.TemplateResponse(
        request,
        "estimates/_row.html",
        {"request": request, "inv": inv, "item": item, "refs": refs_map[item.id]},
    )


@router.post("/{invoice_id}/bulk-confirm-auto")
async def bulk_confirm_auto(
    invoice_id: int,
    request: Request,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    """Подтвердить все позиции с estimation_method=auto_high одним кликом."""
    inv = await invoice_repo.get_invoice_with_items(session, invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Смета не найдена")
    confirmed_count = 0
    for it in inv.items:
        if it.was_confirmed:
            continue
        if it.estimation_method == "auto_high" and (it.unit_price or 0) > 0:
            await invoice_repo.confirm_item(session, invoice_id, it.id)
            confirmed_count += 1
    inv = await invoice_repo.get_invoice_with_items(session, invoice_id)
    refs_map = await _refs_for_items(session, inv.items)
    confirmed = sum(1 for i in inv.items if i.was_confirmed)
    total_count = len(inv.items)
    return templates.TemplateResponse(
        request,
        "estimates/_table.html",
        {
            "request": request,
            "inv": inv,
            "items": inv.items,
            "refs_map": refs_map,
            "confirmed_count": confirmed,
            "total_count": total_count,
            "progress_pct": int(round((confirmed / total_count) * 100)) if total_count else 0,
        },
    )


# ---------------- META update (client / object) ----------------


@router.post("/{invoice_id}/meta")
async def update_meta(
    invoice_id: int,
    request: Request,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
    client_name: str = Form(""),
    contact_name: str = Form(""),
    object_name: str = Form(""),
):
    await invoice_repo.update_invoice_meta(
        session,
        invoice_id,
        client_name=client_name or None,
        contact_name=contact_name or None,
        object_name=object_name or None,
    )
    return PlainTextResponse(
        "",
        headers={
            "HX-Trigger": json.dumps(
                {"vilins:toast": {"kind": "success", "message": "Реквизиты сохранены"}}
            )
        },
    )


# ---------------- FINALIZE → PDF ----------------


@router.post("/{invoice_id}/finalize")
async def finalize_estimate(
    invoice_id: int,
    request: Request,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    inv = await invoice_repo.get_invoice_with_items(session, invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Смета не найдена")
    if not all(i.was_confirmed for i in inv.items):
        raise HTTPException(status_code=400, detail="Не все позиции подтверждены")

    PDF_DIR.mkdir(parents=True, exist_ok=True)
    gen = PDFGenerator()
    pdf_bytes = await gen.generate(inv, inv.items)
    pdf_path = PDF_DIR / f"invoice_{inv.id}_{inv.invoice_number.replace('/', '_')}.pdf"
    pdf_path.write_bytes(pdf_bytes)
    await invoice_repo.mark_invoice_completed(session, invoice_id, str(pdf_path))

    # автоматически добавляем как прецедент
    try:
        await reference_repo.import_from_invoice(session, invoice_id)
    except Exception:  # noqa: BLE001
        logger.exception("import_from_invoice failed (non-fatal)")

    return RedirectResponse(f"/estimates/{invoice_id}/done", status_code=303)


@router.get("/{invoice_id}/done")
async def estimate_done(
    invoice_id: int,
    request: Request,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    inv = await invoice_repo.get_invoice_with_items(session, invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Смета не найдена")
    return templates.TemplateResponse(
        request,
        "estimates/done.html",
        {"request": request, "user": user, "inv": inv},
    )


@router.get("/{invoice_id}/pdf")
async def estimate_pdf(
    invoice_id: int,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
    download: int = 0,
):
    inv = await invoice_repo.get_invoice_with_items(session, invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Смета не найдена")
    if not inv.pdf_path or not Path(inv.pdf_path).is_file():
        # сгенерировать на лету
        gen = PDFGenerator()
        pdf_bytes = await gen.generate(inv, inv.items)
        return Response(
            pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": (
                    f"attachment; filename=invoice_{inv.id}.pdf"
                    if download else f"inline; filename=invoice_{inv.id}.pdf"
                )
            },
        )
    return FileResponse(
        inv.pdf_path,
        media_type="application/pdf",
        filename=f"smeta_{inv.invoice_number.replace('/', '_')}.pdf" if download else None,
        headers={
            "Content-Disposition": (
                f"attachment; filename=smeta_{inv.invoice_number.replace('/', '_')}.pdf"
                if download
                else f"inline; filename=smeta_{inv.invoice_number.replace('/', '_')}.pdf"
            )
        },
    )
