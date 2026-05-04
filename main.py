"""Точка входа Telegram-бота."""

import asyncio
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault
from loguru import logger

from bot.router import setup_routers
from config import config
from db.database import init_db


PUBLIC_COMMANDS = [
    BotCommand(command="start", description="новая смета"),
    BotCommand(command="help", description="справка"),
    BotCommand(command="cancel", description="сбросить текущую смету"),
]

ADMIN_EXTRA_COMMANDS = [
    BotCommand(command="stats", description="статистика"),
    BotCommand(command="import_kp", description="импорт прецедента"),
]


async def _setup_bot_commands(bot: Bot) -> None:
    await bot.set_my_commands(PUBLIC_COMMANDS, scope=BotCommandScopeDefault())
    admin_commands = PUBLIC_COMMANDS + ADMIN_EXTRA_COMMANDS
    for admin_id in config.admin_id_list:
        try:
            await bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))
        except Exception as e:  # noqa: BLE001
            logger.warning("set_my_commands for admin {} failed: {}", admin_id, e)


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

    await _setup_bot_commands(bot)

    logger.info("Bot starting polling…")
    await dp.start_polling(bot, drop_pending_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
