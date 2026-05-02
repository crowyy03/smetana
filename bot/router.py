"""Сборка роутеров и middleware."""

from aiogram import Dispatcher

from bot.handlers import admin, confirm, estimation, manual, start, upload
from bot.middlewares import LoggingMiddleware, ThrottleMiddleware


def setup_routers(dp: Dispatcher) -> None:
    dp.update.middleware(LoggingMiddleware())
    dp.update.middleware(ThrottleMiddleware())
    dp.include_router(start.router)
    dp.include_router(admin.router)
    dp.include_router(confirm.router)
    dp.include_router(estimation.router)
    dp.include_router(manual.router)
    dp.include_router(upload.router)
