"""Перехват любых нерелевантных сообщений в активном FSM-сценарии.

Подключается ПОСЛЕДНИМ роутером. Если сообщение в активном состоянии не было
обработано ни одним из специализированных хендлеров (например, новый файл /
текст пришёл в момент работы со сметой) — показываем подсказку и ждём /cancel.
Это защищает от случайной перезаписи черновика и от мусорных DB-записей.
"""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.states import AdminImportStates, EstimationStates

router = Router(name="guard")


_BUSY_HINTS: dict[str, str] = {
    EstimationStates.parsing.state: "идёт разбор файла",
    EstimationStates.confirming_position.state: "подтверждение позиций — пользуйся кнопками под карточкой",
    EstimationStates.manual_price_entry.state: "ожидаю ввод цены за единицу",
    EstimationStates.editing_quantity.state: "ожидаю ввод количества",
    EstimationStates.adding_position_name.state: "ожидаю название новой позиции",
    EstimationStates.adding_position_qty.state: "ожидаю количество для новой позиции",
    EstimationStates.adding_position_price.state: "ожидаю цену для новой позиции",
    EstimationStates.entering_object_name.state: "ожидаю название объекта (или /skip)",
    EstimationStates.entering_client_name.state: "ожидаю заказчика (или /skip)",
    EstimationStates.entering_contact_name.state: "ожидаю контактное лицо (или /skip)",
    EstimationStates.final_review.state: "финальная сводка — подтверди или вернись к позициям",
    AdminImportStates.confirming_import.state: "подтверди импорт прецедента кнопкой",
}


_BUSY_STATES = [
    EstimationStates.parsing,
    EstimationStates.confirming_position,
    EstimationStates.manual_price_entry,
    EstimationStates.editing_quantity,
    EstimationStates.adding_position_name,
    EstimationStates.adding_position_qty,
    EstimationStates.adding_position_price,
    EstimationStates.entering_object_name,
    EstimationStates.entering_client_name,
    EstimationStates.entering_contact_name,
    EstimationStates.final_review,
    AdminImportStates.confirming_import,
]


@router.message(StateFilter(*_BUSY_STATES))
async def busy_guard(message: Message, state: FSMContext) -> None:
    cur = await state.get_state()
    hint = _BUSY_HINTS.get(cur or "", "идёт работа над сметой")
    await message.answer(
        f"⏸ Сейчас {hint}.\n"
        "Заверши текущий шаг или /cancel — сбросить и начать заново.",
    )
