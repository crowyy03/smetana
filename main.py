"""Точка входа Telegram-бота."""

import asyncio
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from loguru import logger

from bot.router import setup_routers
from config import config
from db.database import init_db


def _setup_logging() -> None:
    Path("logs").mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.add(sys.stderr, level=config.LOG_LEVEL)
    logger.add(config.LOG_FILE, rotation="10 MB", retention="7 days", level=config.LOG_LEVEL)


async def main() -> None:
    _setup_logging()
    if not config.BOT_TOKEN:
        logger.error("Укажите BOT_TOKEN в .env")
        sys.exit(1)

    Path("data/reference_kp").mkdir(parents=True, exist_ok=True)
    Path("data/extracted").mkdir(parents=True, exist_ok=True)
    Path("data/sample_requests").mkdir(parents=True, exist_ok=True)
    await init_db()

    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    setup_routers(dp)

    logger.info("Bot starting polling…")
    await dp.start_polling(bot, drop_pending_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
