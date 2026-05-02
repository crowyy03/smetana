"""Команды /start и /help."""

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.states import EstimationStates
from config import config

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(EstimationStates.waiting_for_input)
    extra = ""
    if message.from_user and message.from_user.id in config.admin_id_list:
        extra = "\nАдмин: /import_kp, /stats\n"
    await message.answer(
        "Привет! Соберу коммерческое предложение из твоего файла или текста.\n\n"
        "Цены берутся только из нашей базы исторических КП (прецеденты + поиск по смыслу). "
        "Если аналогов мало — попросим цену вручную.\n\n"
        "Пришли .xlsx, .pdf, .docx или опиши позиции текстом.\n\n"
        "/help — справка\n"
        "/cancel — сбросить текущую смету"
        + extra,
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "1. Загрузи файл или пришли список позиций текстом.\n"
        "2. Для каждой позиции проверь цену и нажми «Подтвердить» (или введи цену вручную).\n"
        "3. Заполни объект / заказчика и сгенерируй PDF.\n\n"
        "Прецеденты пополняются: CLI `python scripts/import_history.py`, админ-команда /import_kp, "
        "и автоматически после выдачи PDF.",
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(EstimationStates.waiting_for_input)
    await message.answer("Сбросил. Можно начать заново — пришли файл или текст.")
