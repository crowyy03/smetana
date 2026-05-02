"""Маршруты аутентификации: вход и выход."""

from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from config import config
from db import user_repo
from web.auth import (
    SESSION_COOKIE_NAME,
    decode_session,
    encode_session,
    verify_password,
)
from web.deps import get_session
from web.templating import templates

router = APIRouter()


@router.get("/login")
async def login_page(
    request: Request,
    next: str = "/",
    session: AsyncSession = Depends(get_session),
    session_cookie: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
):
    if session_cookie and decode_session(session_cookie):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        request,
        "auth/login.html",
        {"request": request, "next": next, "error": None},
    )


@router.post("/login")
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next: str = Form(default="/"),
    session: AsyncSession = Depends(get_session),
):
    user = await user_repo.get_by_email(session, email)
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {
                "request": request,
                "next": next,
                "error": "Неверный e-mail или пароль.",
                "email": email,
            },
            status_code=400,
        )
    await user_repo.touch_login(session, user.id)
    token = encode_session(user.id)
    response = RedirectResponse(next or "/", status_code=303)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=config.WEB_SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=False,  # включить True за HTTPS-прокси
    )
    return response


@router.post("/logout")
async def logout():
    response = RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return response


@router.get("/register")
async def register_page(
    request: Request,
    session_cookie: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
):
    if session_cookie and decode_session(session_cookie):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        request,
        "auth/register.html",
        {"request": request, "error": None, "values": {}},
    )


@router.post("/register")
async def register_submit(
    request: Request,
    email: str = Form(...),
    full_name: str = Form(""),
    password: str = Form(...),
    confirm_password: str = Form(...),
    session: AsyncSession = Depends(get_session),
):
    from web.auth import hash_password

    values = {"email": email, "full_name": full_name}
    email_norm = (email or "").strip().lower()

    def _err(msg: str, code: int = 400):
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            {"request": request, "error": msg, "values": values},
            status_code=code,
        )

    if "@" not in email_norm or len(email_norm) < 5:
        return _err("Укажите корректный e-mail.")
    if len(password) < 8:
        return _err("Пароль должен быть минимум 8 символов.")
    if password != confirm_password:
        return _err("Пароли не совпадают.")
    if not full_name.strip():
        return _err("Укажите имя.")

    existing = await user_repo.get_by_email(session, email_norm)
    if existing is not None:
        return _err("Пользователь с таким e-mail уже зарегистрирован.")

    user = await user_repo.create_user(
        session,
        email=email_norm,
        password_hash=hash_password(password),
        full_name=full_name,
        role="estimator",
    )
    await user_repo.touch_login(session, user.id)
    token = encode_session(user.id)
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=config.WEB_SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=False,
    )
    return response
