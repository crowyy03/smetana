"""FastAPI dependencies: сессия БД, текущий пользователь, авторизация."""

from __future__ import annotations

from typing import AsyncGenerator

from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import AsyncSessionLocal
from db import user_repo
from db.models import User
from web.auth import SESSION_COOKIE_NAME, decode_session


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as s:
        yield s


async def get_current_user_optional(
    request: Request,
    session_cookie: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    session: AsyncSession = Depends(get_session),
) -> User | None:
    if not session_cookie:
        return None
    uid = decode_session(session_cookie)
    if not uid:
        return None
    user = await user_repo.get_by_id(session, uid)
    if user is None or not user.is_active:
        return None
    request.state.current_user = user
    return user


async def require_user(user: User | None = Depends(get_current_user_optional)) -> User:
    if user is None:
        # перехватим в обработчике, чтобы вернуть RedirectResponse
        raise HTTPException(status_code=status.HTTP_307_TEMPORARY_REDIRECT, headers={"Location": "/login"})
    return user


async def require_admin(user: User = Depends(require_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return user
