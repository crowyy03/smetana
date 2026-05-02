"""Админ: импорт КП, статистика."""

from __future__ import annotations

from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.filters import IsAdmin
from bot.formatting import fmt_money
from bot.keyboards.inline import admin_import_confirm_keyboard
from bot.states import AdminImportStates
from config import config
from core.parsers.types import ParseSource
from core.parsers.universal import UniversalParser
from core.reference_db.importer import import_single_kp_file
from db.database import AsyncSessionLocal
from db import invoice_repo as inv_repo

router = Router(name="admin")

REF_DIR = Path("data/reference_kp")
EXTRACTED = Path("data/extracted")


@router.message(Command("stats"), IsAdmin())
async def cmd_stats(message: Message) -> None:
    async with AsyncSessionLocal() as session:
        s = await inv_repo.stats_admin(session)
    await message.answer(
        f"Смет сегодня: {s['invoices_today']}\n"
        f"Смет за месяц: {s['invoices_month']}\n"
        f"Сумма за месяц: {fmt_money(s['total_month'])}",
    )


@router.message(Command("import_kp"), IsAdmin())
async def cmd_import_kp(message: Message, state: FSMContext) -> None:
    if not config.ADMIN_IDS:
        await message.answer("ADMIN_IDS не задан в .env")
        return
    await state.set_state(AdminImportStates.waiting_file)
    await message.answer("Пришли PDF / xlsx / docx исторического КП. Файл сохраню в data/reference_kp/.")


@router.message(AdminImportStates.waiting_file, F.document, IsAdmin())
async def adm_on_doc(message: Message, state: FSMContext, bot: Bot) -> None:
    doc = message.document
    if not doc or not doc.file_name:
        return
    name = doc.file_name
    low = name.lower()
    if not any(low.endswith(ext) for ext in (".pdf", ".xlsx", ".docx")):
        await message.answer("Нужен .pdf, .xlsx или .docx")
        return

    REF_DIR.mkdir(parents=True, exist_ok=True)
    dest = REF_DIR / name
    await bot.download(doc, destination=dest)

    fmt = "pdf" if low.endswith(".pdf") else "xlsx" if low.endswith(".xlsx") else "docx"
    preview = ""
    try:
        pr = await UniversalParser().parse(ParseSource(file_path=dest, file_format=fmt))
        preview = f"Быстрый разбор: **{len(pr.items)}** строк (универсальный парсер).\n"
        for it in pr.items[:8]:
            preview += f"• {it.suggested_name[:80]}\n"
        if len(pr.items) > 8:
            preview += "…\n"
    except Exception as e:  # noqa: BLE001
        preview = f"Предпросмотр не вышел ({e}). Импорт всё равно возможен через LLM.\n"

    await state.update_data(pending_kp_path=str(dest.resolve()))
    await state.set_state(AdminImportStates.confirming_import)
    await message.answer(
        preview + "\nИмпорт через Claude создаст записи в БД и embeddings.",
        reply_markup=admin_import_confirm_keyboard(),
    )


@router.callback_query(F.data == "adm_imp_cancel", StateFilter(AdminImportStates.confirming_import), IsAdmin())
async def adm_cancel(c: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await c.message.answer("Отменено.")
    await c.answer()


@router.callback_query(F.data == "adm_imp_ok", StateFilter(AdminImportStates.confirming_import), IsAdmin())
async def adm_ok(c: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    path = Path(data.get("pending_kp_path", ""))
    if not path.is_file():
        await c.answer("Файл не найден", show_alert=True)
        return
    await c.message.answer("⏳ Импортирую (LLM + embeddings)…")
    try:
        async with AsyncSessionLocal() as session:
            proj = await import_single_kp_file(session, path, extracted_dir=EXTRACTED, force=False)
    except Exception as e:  # noqa: BLE001
        await c.message.answer(f"❌ Ошибка импорта: {e}")
        await state.clear()
        await c.answer()
        return

    await state.clear()
    n = len(proj.items) if proj else 0
    await c.message.answer(f"✅ Готово: проект «{proj.project_name}», позиций: {n}")
    await c.answer()
