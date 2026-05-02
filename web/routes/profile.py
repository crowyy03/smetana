"""Личный кабинет."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from db import invoice_repo, user_repo
from db.models import User
from web.auth import hash_password, verify_password
from web.deps import get_session, require_user
from web.templating import templates

router = APIRouter()


@router.get("/profile")
async def profile_page(
    request: Request,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
    flash: str | None = None,
    error: str | None = None,
):
    stats = await invoice_repo.stats_for_user(session, user.id)
    return templates.TemplateResponse(
        request,
        "profile.html",
        {
            "request": request,
            "user": user,
            "stats": stats,
            "flash": flash,
            "error": error,
        },
    )


@router.post("/profile")
async def profile_update(
    request: Request,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
    full_name: str = Form(""),
    telegram_user_id: str = Form(""),
    theme_pref: str = Form("system"),
):
    tg_id: int | None = None
    if telegram_user_id.strip():
        try:
            tg_id = int(telegram_user_id.strip())
        except ValueError:
            return RedirectResponse(
                "/profile?error=Telegram%20ID%20должен%20быть%20числом", status_code=303
            )
    await user_repo.update_profile(
        session,
        user.id,
        full_name=full_name,
        telegram_user_id=tg_id,
        theme_pref=theme_pref,
    )
    return RedirectResponse("/profile?flash=Профиль%20обновлён", status_code=303)


@router.post("/profile/password")
async def password_update(
    request: Request,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
):
    if not verify_password(current_password, user.password_hash):
        return RedirectResponse("/profile?error=Текущий%20пароль%20неверный", status_code=303)
    if new_password != confirm_password:
        return RedirectResponse("/profile?error=Пароли%20не%20совпадают", status_code=303)
    if len(new_password) < 8:
        return RedirectResponse("/profile?error=Минимум%208%20символов", status_code=303)
    await user_repo.update_password(session, user.id, hash_password(new_password))
    return RedirectResponse("/profile?flash=Пароль%20обновлён", status_code=303)
