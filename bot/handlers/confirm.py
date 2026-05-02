"""Финальный PDF и пост-обработка."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery
from loguru import logger

from bot.handlers.estimation import show_position_card
from bot.states import EstimationStates
from core.pdf.generator import PDFGenerator
from db.database import AsyncSessionLocal
from db import invoice_repo as inv_repo
from db import reference_repo as ref_repo

router = Router(name="confirm")


@router.callback_query(F.data == "est_back_items")
async def cb_back_items(c: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(EstimationStates.confirming_position)
    await show_position_card(c, state, edit=False)
    await c.answer()


@router.callback_query(F.data == "est_pdf")
async def cb_generate_pdf(c: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    inv_id = int(data.get("invoice_id") or 0)
    async with AsyncSessionLocal() as session:
        ok = await inv_repo.all_items_confirmed(session, inv_id)
        if not ok:
            await c.answer("Сначала подтверди все позиции.", show_alert=True)
            return
        inv = await inv_repo.get_invoice_with_items(session, inv_id)
    if not inv:
        await c.answer("Смета не найдена", show_alert=True)
        return

    gen = PDFGenerator()
    pdf_bytes = await gen.generate(inv, list(inv.items))

    fname = f"KP_{inv.invoice_number.replace('/', '-')}.pdf"
    await c.message.answer_document(
        BufferedInputFile(pdf_bytes, filename=fname),
        caption=f"КП {inv.invoice_number}",
    )

    async with AsyncSessionLocal() as session:
        await inv_repo.mark_invoice_completed(session, inv_id, pdf_path=None)
        try:
            await ref_repo.import_from_invoice(session, inv_id)
        except Exception:  # noqa: BLE001
            logger.exception("import_from_invoice failed invoice_id={}", inv_id)

    await state.clear()
    await state.set_state(EstimationStates.waiting_for_input)
    await c.message.answer("Готово. Подтверждённые позиции добавлены в базу прецедентов. /start — новая смета.")
    await c.answer()
