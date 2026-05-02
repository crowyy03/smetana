"""Приём файлов и текста → парсинг → оценка → черновик сметы."""

from __future__ import annotations

import json
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.handlers.estimation import show_position_card
from bot.states import EstimationStates
from config import config
from core.estimator.price_estimator import PriceEstimator
from core.parsers.text_parser import TextParser
from core.parsers.types import ParseSource
from core.parsers.universal import UniversalParser
from db.database import AsyncSessionLocal
from db import invoice_repo as inv_repo
from loguru import logger

router = Router(name="upload")
TMP = Path("/tmp/smeta_bot")


def _user_dir(uid: int) -> Path:
    p = TMP / str(uid)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _detect_format(name: str) -> str:
    n = name.lower()
    if n.endswith(".xlsx"):
        return "xlsx"
    if n.endswith(".xls"):
        return "xls"
    if n.endswith(".pdf"):
        return "pdf"
    if n.endswith(".docx"):
        return "docx"
    return "text"


def _items_payload(parse_items, results) -> list[dict]:
    if len(results) != len(parse_items):
        logger.warning("estimate_batch length mismatch, fallback manual")
        results = PriceEstimator.fallback_manual(parse_items)
    payload = []
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


@router.message(StateFilter(EstimationStates.waiting_for_input), F.document)
async def on_document(message: Message, state: FSMContext, bot: Bot) -> None:
    doc = message.document
    if not doc or not doc.file_name:
        return
    fmt = _detect_format(doc.file_name)
    if fmt == "xls":
        await message.answer("Формат .xls не поддерживается — конвертируй в .xlsx.")
        return

    await state.set_state(EstimationStates.parsing)
    await message.answer("⏳ Загружаю и анализирую файл...")

    uid = message.from_user.id if message.from_user else 0
    dest = _user_dir(uid) / (doc.file_name or "upload.bin")
    try:
        await bot.download(doc, destination=dest)
    except Exception as e:  # noqa: BLE001
        logger.exception("download")
        await message.answer(f"❌ Не удалось скачать файл: {e}")
        await state.set_state(EstimationStates.waiting_for_input)
        return

    src = ParseSource(file_path=dest, file_format=fmt)
    parser = UniversalParser()
    try:
        parse_result = await parser.parse(src)
    except Exception as e:  # noqa: BLE001
        await message.answer(
            f"❌ Не смог разобрать файл: {e}\n\nПришли текстом или попробуй другой формат.",
        )
        await state.set_state(EstimationStates.waiting_for_input)
        return

    if not parse_result.items:
        await message.answer("❌ В файле не нашёл позиций.")
        await state.set_state(EstimationStates.waiting_for_input)
        return

    notes = "\n".join(parse_result.parser_notes) if parse_result.parser_notes else ""
    if notes:
        await message.answer(f"⚠️ Замечания парсера:\n{notes}")

    await message.answer(f"✅ Нашёл {len(parse_result.items)} позиций. Подбираю цены по прецедентам...")

    meta = parse_result.project_metadata or {}
    ctx = json.dumps(meta, ensure_ascii=False) if meta else ""

    async with AsyncSessionLocal() as session:
        try:
            est = PriceEstimator()
            results = await est.estimate_batch(session, parse_result.items, project_context=ctx)
        except Exception:  # noqa: BLE001
            logger.exception("estimate")
            results = PriceEstimator.fallback_manual(parse_result.items)

        payload = _items_payload(parse_result.items, results)

        inv = await inv_repo.create_draft_invoice(
            session,
            telegram_user_id=message.from_user.id if message.from_user else 0,
            telegram_username=message.from_user.username if message.from_user else None,
            source_file_name=doc.file_name,
            source_format=fmt,
            items_payload=payload,
        )

    await state.update_data(invoice_id=inv.id, current_index=0)
    await state.set_state(EstimationStates.confirming_position)
    await show_position_card(message, state)


@router.message(EstimationStates.waiting_for_input, F.text, ~F.text.startswith("/"))
async def on_text(message: Message, state: FSMContext) -> None:
    if not config.ANTHROPIC_API_KEY:
        await message.answer("Нужен ANTHROPIC_API_KEY для разбора текста.")
        return

    await state.set_state(EstimationStates.parsing)
    await message.answer("⏳ Разбираю текст...")
    parse_result = await TextParser().parse(message.text or "")
    if not parse_result.items:
        notes = "\n".join(parse_result.parser_notes) if parse_result.parser_notes else ""
        msg = "❌ Не извлёк позиции из текста."
        if notes:
            msg += f"\n\nПричина: {notes}"
        await message.answer(msg)
        await state.set_state(EstimationStates.waiting_for_input)
        return

    ctx = json.dumps(parse_result.project_metadata or {}, ensure_ascii=False)

    async with AsyncSessionLocal() as session:
        est = PriceEstimator()
        results = await est.estimate_batch(session, parse_result.items, project_context=ctx)
        payload = _items_payload(parse_result.items, results)
        inv = await inv_repo.create_draft_invoice(
            session,
            telegram_user_id=message.from_user.id if message.from_user else 0,
            telegram_username=message.from_user.username if message.from_user else None,
            source_file_name=None,
            source_format="text",
            items_payload=payload,
        )

    await state.update_data(invoice_id=inv.id, current_index=0)
    await state.set_state(EstimationStates.confirming_position)
    await show_position_card(message, state)
