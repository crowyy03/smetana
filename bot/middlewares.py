"""Логирование и простой антиспам."""

import time
from collections import defaultdict
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from loguru import logger

_last_ts: dict[int, float] = defaultdict(float)
_MIN_INTERVAL = 0.4


class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        t0 = time.perf_counter()
        uid = None
        if isinstance(event, Message) and event.from_user:
            uid = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            uid = event.from_user.id
        try:
            return await handler(event, data)
        finally:
            ms = (time.perf_counter() - t0) * 1000
            logger.debug("update user={} elapsed_ms={:.1f}", uid, ms)


class ThrottleMiddleware(BaseMiddleware):
    """Не чаще _MIN_INTERVAL с одного user_id для message/callback."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        uid = None
        if isinstance(event, Message) and event.from_user:
            uid = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            uid = event.from_user.id
        if uid is None:
            return await handler(event, data)
        now = time.monotonic()
        last = _last_ts[uid]
        if now - last < _MIN_INTERVAL:
            if isinstance(event, CallbackQuery):
                await event.answer("Слишком часто, подождите секунду.", show_alert=False)
            return None
        _last_ts[uid] = now
        return await handler(event, data)
