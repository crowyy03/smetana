"""Фильтры aiogram."""

from aiogram.filters import BaseFilter
from aiogram.types import Message, TelegramObject

from config import config


class IsAdmin(BaseFilter):
    """Пользователь в ADMIN_IDS."""

    async def __call__(self, event: TelegramObject) -> bool:
        uid: int | None = None
        if isinstance(event, Message):
            uid = event.from_user.id if event.from_user else None
        else:
            from aiogram.types import CallbackQuery

            if isinstance(event, CallbackQuery) and event.from_user:
                uid = event.from_user.id
        if uid is None:
            return False
        return uid in config.admin_id_list
