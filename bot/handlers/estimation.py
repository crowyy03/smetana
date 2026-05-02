"""Пошаговое подтверждение позиций."""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.formatting import fmt_money
from bot.keyboards.inline import build_position_keyboard, final_review_keyboard
from bot.states import EstimationStates
from db.database import AsyncSessionLocal
from db import invoice_repo as inv_repo
from db.reference_repo import get_reference_items_by_ids

router = Router(name="estimation")


async def show_position_card(target: Message | CallbackQuery, state: FSMContext, *, edit: bool = False) -> None:
    data = await state.get_data()
    inv_id = int(data.get("invoice_id") or 0)
    idx = int(data.get("current_index") or 0)
    async with AsyncSessionLocal() as session:
        items = await inv_repo.list_invoice_items(session, inv_id)
        all_ok = await inv_repo.all_items_confirmed(session, inv_id)
    if not items:
        text = "Нет позиций."
        if isinstance(target, CallbackQuery):
            await target.message.answer(text)
            await target.answer()
        else:
            await target.answer(text)
        return
    idx = max(0, min(idx, len(items) - 1))
    await state.update_data(current_index=idx)
    item = items[idx]

    emoji = {"auto_high": "🟢", "auto_medium": "🟡", "needs_manual": "🔴"}.get(item.estimation_method, "⚪")
    text_lines = [
        f"{emoji} Позиция {idx + 1}/{len(items)}",
        "",
        f"📋 {item.name}",
        f"📝 {item.description}",
        "",
        f"📦 Количество: {item.quantity} {item.unit}",
    ]
    if item.estimation_method != "needs_manual":
        text_lines += [
            "",
            f"💰 Цена за ед.: {fmt_money(item.unit_price)}",
            f"💵 Итого: {fmt_money(item.total_price)}",
            "",
            "🔍 На основе:",
        ]
        try:
            ref_ids = json.loads(item.reference_item_ids or "[]")
        except json.JSONDecodeError:
            ref_ids = []
        async with AsyncSessionLocal() as session:
            refs = await get_reference_items_by_ids(session, ref_ids[:3])
        for ref in refs:
            pname = ref.project.project_name if ref.project else ""
            text_lines.append(f"• {pname} — {ref.name}: {fmt_money(ref.unit_price)}/{ref.unit}")
        if item.estimation_reasoning:
            text_lines += ["", f"💡 {item.estimation_reasoning}"]
    else:
        text_lines += ["", "⚠️ Нет уверенных аналогов в истории. Введи цену вручную."]

    text = "\n".join(text_lines)
    kb = build_position_keyboard(item, idx, len(items), all_ok)

    if isinstance(target, CallbackQuery):
        if edit:
            await target.message.edit_text(text, reply_markup=kb)
        else:
            await target.message.answer(text, reply_markup=kb)
        await target.answer()
    else:
        await target.answer(text, reply_markup=kb)


@router.callback_query(F.data == "noop")
async def cb_noop(c: CallbackQuery) -> None:
    await c.answer()


@router.callback_query(F.data.startswith("est_nav:"))
async def cb_nav(c: CallbackQuery, state: FSMContext) -> None:
    idx = int(c.data.split(":")[1])
    await state.update_data(current_index=idx)
    await show_position_card(c, state, edit=True)


@router.callback_query(F.data.startswith("est_confirm:"))
async def cb_confirm(c: CallbackQuery, state: FSMContext) -> None:
    item_id = int(c.data.split(":")[1])
    data = await state.get_data()
    inv_id = int(data["invoice_id"])
    async with AsyncSessionLocal() as session:
        await inv_repo.confirm_item(session, inv_id, item_id)
        items = await inv_repo.list_invoice_items(session, inv_id)
        next_i = next((i for i, it in enumerate(items) if not it.was_confirmed), None)
    if next_i is not None:
        await state.update_data(current_index=next_i)
    await show_position_card(c, state, edit=True)


@router.callback_query(F.data.startswith("est_edit_price:"))
async def cb_edit_price(c: CallbackQuery, state: FSMContext) -> None:
    item_id = int(c.data.split(":")[1])
    await state.update_data(pending_item_id=item_id)
    await state.set_state(EstimationStates.manual_price_entry)
    await c.message.answer("Введи новую цену за единицу (число, например 4280 или 4280.50):")
    await c.answer()


@router.message(EstimationStates.manual_price_entry, F.text)
async def msg_manual_price(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    inv_id = int(data["invoice_id"])
    item_id = int(data["pending_item_id"])
    raw = (message.text or "").replace(" ", "").replace(",", ".")
    try:
        price = Decimal(raw)
        if price <= 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        await message.answer("❌ Не понял число. Пример: 4280")
        return
    async with AsyncSessionLocal() as session:
        await inv_repo.update_item_price(session, inv_id, item_id, price, was_modified=True)
    await state.set_state(EstimationStates.confirming_position)
    await message.answer("Цена обновлена.")
    await show_position_card(message, state)


@router.callback_query(F.data.startswith("est_manual_price:"))
async def cb_manual_price(c: CallbackQuery, state: FSMContext) -> None:
    item_id = int(c.data.split(":")[1])
    await state.update_data(pending_item_id=item_id)
    await state.set_state(EstimationStates.manual_price_entry)
    await c.message.answer("Введи цену за единицу (руб.):")
    await c.answer()


@router.callback_query(F.data.startswith("est_edit_qty:"))
async def cb_edit_qty(c: CallbackQuery, state: FSMContext) -> None:
    item_id = int(c.data.split(":")[1])
    await state.update_data(pending_item_id=item_id)
    await state.set_state(EstimationStates.editing_quantity)
    await c.message.answer("Введи новое количество:")
    await c.answer()


@router.message(EstimationStates.editing_quantity, F.text)
async def msg_edit_qty(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    inv_id = int(data["invoice_id"])
    item_id = int(data["pending_item_id"])
    try:
        q = Decimal((message.text or "").replace(" ", "").replace(",", "."))
        if q <= 0:
            raise ValueError
    except Exception:  # noqa: BLE001
        await message.answer("Нужно положительное число.")
        return
    async with AsyncSessionLocal() as session:
        await inv_repo.update_item_quantity(session, inv_id, item_id, q)
    await state.set_state(EstimationStates.confirming_position)
    await message.answer("Количество обновлено.")
    await show_position_card(message, state)


@router.callback_query(F.data.startswith("est_delete:"))
async def cb_delete(c: CallbackQuery, state: FSMContext) -> None:
    item_id = int(c.data.split(":")[1])
    data = await state.get_data()
    inv_id = int(data["invoice_id"])
    async with AsyncSessionLocal() as session:
        await inv_repo.delete_item(session, inv_id, item_id)
        items = await inv_repo.list_invoice_items(session, inv_id)
    if not items:
        await state.clear()
        await c.message.answer("Смета пуста. /start")
        await c.answer()
        return
    await state.update_data(current_index=0)
    await show_position_card(c, state, edit=True)


@router.callback_query(F.data.startswith("est_all_refs:"))
async def cb_all_refs(c: CallbackQuery, state: FSMContext) -> None:
    item_id = int(c.data.split(":")[1])
    async with AsyncSessionLocal() as session:
        item = await inv_repo.get_invoice_item(session, item_id)
        if not item:
            await c.answer("Нет позиции", show_alert=True)
            return
        try:
            ref_ids = json.loads(item.reference_item_ids or "[]")
        except json.JSONDecodeError:
            ref_ids = []
        refs = await get_reference_items_by_ids(session, ref_ids)
    lines = [f"🔍 Аналоги для «{item.name}»:\n"]
    for i, ref in enumerate(refs, 1):
        pname = ref.project.project_name if ref.project else ""
        lines.append(f"{i}. {pname} — {ref.name}")
        lines.append(f"   {fmt_money(ref.unit_price)}/{ref.unit} × {ref.quantity} = {fmt_money(ref.total_price)}\n")
    await c.message.answer("\n".join(lines))
    await c.answer()


@router.callback_query(F.data == "est_add")
async def cb_add(c: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(EstimationStates.adding_position_name)
    await c.message.answer("Введи название новой позиции:")
    await c.answer()


@router.message(EstimationStates.adding_position_name, F.text)
async def msg_add_name(message: Message, state: FSMContext) -> None:
    await state.update_data(pending_name=message.text.strip())
    await state.set_state(EstimationStates.adding_position_qty)
    await message.answer("Количество:")


@router.message(EstimationStates.adding_position_qty, F.text)
async def msg_add_qty(message: Message, state: FSMContext) -> None:
    try:
        q = Decimal((message.text or "").replace(",", ".").replace(" ", ""))
    except Exception:  # noqa: BLE001
        await message.answer("Число количества.")
        return
    await state.update_data(pending_qty=str(q))
    await state.set_state(EstimationStates.adding_position_price)
    await message.answer("Цена за единицу (руб.):")


@router.message(EstimationStates.adding_position_price, F.text)
async def msg_add_price(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    inv_id = int(data["invoice_id"])
    name = str(data.get("pending_name", ""))
    qty = Decimal(str(data.get("pending_qty", "1")))
    try:
        price = Decimal((message.text or "").replace(",", ".").replace(" ", ""))
    except Exception:  # noqa: BLE001
        await message.answer("Число цены.")
        return
    async with AsyncSessionLocal() as session:
        await inv_repo.add_manual_item(
            session,
            inv_id,
            name=name,
            description=name,
            quantity=qty,
            unit="шт.",
            unit_price=price,
            section=1,
        )
    await state.set_state(EstimationStates.confirming_position)
    await message.answer("Позиция добавлена.")
    await show_position_card(message, state)


@router.callback_query(F.data == "est_to_client")
async def cb_to_client(c: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    inv_id = int(data["invoice_id"])
    async with AsyncSessionLocal() as session:
        ok = await inv_repo.all_items_confirmed(session, inv_id)
    if not ok:
        await c.answer("Сначала подтверди все позиции", show_alert=True)
        return
    await state.set_state(EstimationStates.entering_object_name)
    await c.message.answer("Название объекта (или /skip):")
    await c.answer()


@router.message(EstimationStates.entering_object_name, F.text)
async def msg_object(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    inv_id = int(data["invoice_id"])
    t = (message.text or "").strip()
    if not t.startswith("/skip"):
        async with AsyncSessionLocal() as session:
            await inv_repo.update_invoice_meta(session, inv_id, object_name=t)
    await state.set_state(EstimationStates.entering_client_name)
    await message.answer("Заказчик (организация или ФИО, /skip чтобы пропустить):")


@router.message(EstimationStates.entering_client_name, F.text)
async def msg_client_name(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    inv_id = int(data["invoice_id"])
    t = (message.text or "").strip()
    if not t.startswith("/skip"):
        async with AsyncSessionLocal() as session:
            await inv_repo.update_invoice_meta(session, inv_id, client_name=t)
    await state.set_state(EstimationStates.entering_contact_name)
    await message.answer("Контактное лицо (/skip чтобы пропустить):")


@router.message(EstimationStates.entering_contact_name, F.text)
async def msg_contact(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    inv_id = int(data["invoice_id"])
    t = (message.text or "").strip()
    async with AsyncSessionLocal() as session:
        if not t.startswith("/skip"):
            await inv_repo.update_invoice_meta(session, inv_id, contact_name=t)
        inv = await inv_repo.get_invoice_with_items(session, inv_id)
    assert inv
    lines = [f"• {it.name}: {it.quantity} {it.unit} × {fmt_money(it.unit_price)} = {fmt_money(it.total_price)}" for it in inv.items]
    await state.set_state(EstimationStates.final_review)
    await message.answer(
        "✅ Сводка перед PDF:\n\n" + "\n".join(lines[:40])
        + f"\n\nРаздел 1: {fmt_money(inv.total_section1)}\nРаздел 2: {fmt_money(inv.total_section2)}\nИТОГО: {fmt_money(inv.total_amount)}",
        reply_markup=final_review_keyboard(),
    )
