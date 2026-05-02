"""CRUD для пользователей веб-интерфейса."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User


async def get_by_id(session: AsyncSession, user_id: int) -> User | None:
    return await session.get(User, user_id)


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    r = await session.execute(select(User).where(User.email == email.strip().lower()))
    return r.scalar_one_or_none()


async def list_all(session: AsyncSession) -> Sequence[User]:
    r = await session.execute(select(User).order_by(User.id))
    return r.scalars().all()


async def create_user(
    session: AsyncSession,
    *,
    email: str,
    password_hash: str,
    full_name: str = "",
    role: str = "estimator",
    telegram_user_id: int | None = None,
) -> User:
    u = User(
        email=email.strip().lower(),
        password_hash=password_hash,
        full_name=full_name.strip(),
        role=role,
        telegram_user_id=telegram_user_id,
    )
    session.add(u)
    await session.commit()
    await session.refresh(u)
    return u


async def update_password(session: AsyncSession, user_id: int, password_hash: str) -> None:
    await session.execute(update(User).where(User.id == user_id).values(password_hash=password_hash))
    await session.commit()


async def update_profile(
    session: AsyncSession,
    user_id: int,
    *,
    full_name: str | None = None,
    telegram_user_id: int | None = None,
    theme_pref: str | None = None,
) -> None:
    data: dict[str, object] = {}
    if full_name is not None:
        data["full_name"] = full_name.strip()
    if telegram_user_id is not None:
        data["telegram_user_id"] = telegram_user_id or None
    if theme_pref is not None and theme_pref in ("system", "day", "night"):
        data["theme_pref"] = theme_pref
    if not data:
        return
    await session.execute(update(User).where(User.id == user_id).values(**data))
    await session.commit()


async def touch_login(session: AsyncSession, user_id: int) -> None:
    await session.execute(
        update(User).where(User.id == user_id).values(last_login_at=datetime.now(timezone.utc))
    )
    await session.commit()
