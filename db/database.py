"""Инициализация async SQLAlchemy."""

from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import config
from db.models import Base

_engine = create_async_engine(
    config.DATABASE_URL,
    echo=False,
)
AsyncSessionLocal = async_sessionmaker(
    _engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def init_db() -> None:
    """Создать директорию для SQLite и таблицы."""
    url = config.DATABASE_URL
    if "sqlite" in url:
        # sqlite+aiosqlite:///./data/smeta_bot.db
        for prefix in ("sqlite+aiosqlite:///", "sqlite+aiosqlite:////"):
            if url.startswith(prefix):
                rest = url[len(prefix) :]
                if rest.startswith("./"):
                    path = Path(rest)
                    path.parent.mkdir(parents=True, exist_ok=True)
                break
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
