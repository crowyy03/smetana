"""Inline-клавиатуры v2."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from db.models import InvoiceItem


def build_position_keyboard(item: InvoiceItem, index: int, total: int, all_confirmed: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if item.estimation_method != "needs_manual":
        rows.append(
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"est_confirm:{item.id}"),
                InlineKeyboardButton(text="✏️ Изменить цену", callback_data=f"est_edit_price:{item.id}"),
            ]
        )
    else:
        rows.append([InlineKeyboardButton(text="💰 Ввести цену", callback_data=f"est_manual_price:{item.id}")])

    rows.append(
        [
            InlineKeyboardButton(text="📊 Изменить кол-во", callback_data=f"est_edit_qty:{item.id}"),
            InlineKeyboardButton(text="🔍 Все аналоги", callback_data=f"est_all_refs:{item.id}"),
        ]
    )
    rows.append([InlineKeyboardButton(text="❌ Удалить позицию", callback_data=f"est_delete:{item.id}")])

    nav: list[InlineKeyboardButton] = []
    if index > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"est_nav:{index-1}"))
    nav.append(InlineKeyboardButton(text=f"{index+1}/{total}", callback_data="noop"))
    if index < total - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"est_nav:{index+1}"))
    rows.append(nav)

    rows.append([InlineKeyboardButton(text="➕ Добавить позицию", callback_data="est_add")])

    if all_confirmed:
        rows.append([InlineKeyboardButton(text="✅ Далее (реквизиты)", callback_data="est_to_client")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def final_review_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📄 Сгенерировать PDF", callback_data="est_pdf"),
                InlineKeyboardButton(text="◀ К позициям", callback_data="est_back_items"),
            ]
        ]
    )


def admin_import_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Импортировать в базу", callback_data="adm_imp_ok"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="adm_imp_cancel"),
            ]
        ]
    )
