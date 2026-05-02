"""FastAPI-приложение веб-интерфейса VILINS Smeta."""

from __future__ import annotations

import sys
from pathlib import Path

# чтобы можно было запускать `python -m uvicorn web.main:app` из корня проекта
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contextlib import asynccontextmanager  # noqa: E402

from fastapi import FastAPI, Request, status  # noqa: E402
from fastapi.exceptions import HTTPException  # noqa: E402
from fastapi.responses import HTMLResponse, RedirectResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from loguru import logger  # noqa: E402

from db import user_repo  # noqa: E402
from db.database import AsyncSessionLocal, init_db  # noqa: E402
from web.auth import SESSION_COOKIE_NAME, decode_session  # noqa: E402
from web.routes import auth as auth_routes  # noqa: E402
from web.routes import estimates as estimates_routes  # noqa: E402
from web.routes import home as home_routes  # noqa: E402
from web.routes import profile as profile_routes  # noqa: E402
from web.templating import templates  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    Path("data").mkdir(parents=True, exist_ok=True)
    Path("logs").mkdir(parents=True, exist_ok=True)
    Path("data/uploads").mkdir(parents=True, exist_ok=True)
    Path("data/pdf").mkdir(parents=True, exist_ok=True)
    await init_db()
    logger.info("Web app started")
    yield


app = FastAPI(
    title="VILINS Smeta",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)


STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.middleware("http")
async def attach_user(request: Request, call_next):
    """Кладёт текущего пользователя в request.state — чтобы шаблоны видели его без явного Depends."""
    request.state.current_user = None
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        uid = decode_session(token)
        if uid:
            async with AsyncSessionLocal() as s:
                user = await user_repo.get_by_id(s, uid)
                if user and user.is_active:
                    request.state.current_user = user
    return await call_next(request)


@app.exception_handler(HTTPException)
async def http_exc_handler(request: Request, exc: HTTPException):
    if exc.status_code in (status.HTTP_307_TEMPORARY_REDIRECT, status.HTTP_303_SEE_OTHER, status.HTTP_302_FOUND):
        location = exc.headers.get("Location") if exc.headers else "/login"
        return RedirectResponse(location or "/login", status_code=status.HTTP_303_SEE_OTHER)
    if exc.status_code == status.HTTP_404_NOT_FOUND:
        return templates.TemplateResponse(
            request,
            "errors/404.html",
            {"request": request},
            status_code=404,
        )
    if exc.status_code == status.HTTP_403_FORBIDDEN:
        return templates.TemplateResponse(
            request,
            "errors/403.html",
            {"request": request, "detail": exc.detail or "Доступ запрещён"},
            status_code=403,
        )
    return HTMLResponse(f"<h1>{exc.status_code}</h1><p>{exc.detail or ''}</p>", status_code=exc.status_code)


app.include_router(auth_routes.router)
app.include_router(home_routes.router)
app.include_router(profile_routes.router)
app.include_router(estimates_routes.router)


if __name__ == "__main__":
    import uvicorn

    from config import config

    uvicorn.run("web.main:app", host=config.WEB_HOST, port=config.WEB_PORT, reload=True)
