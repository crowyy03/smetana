"""Главная страница (дашборд)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Request
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db import invoice_repo, user_repo
from db.models import Invoice, ReferenceProject, User
from web.deps import get_current_user_optional, get_session, require_user
from web.templating import templates

router = APIRouter()


_RU_MONTH_NOM = (
    "январе", "феврале", "марте", "апреле", "мае", "июне",
    "июле", "августе", "сентябре", "октябре", "ноябре", "декабре",
)


@router.get("/")
async def home_page(
    request: Request,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    stats = await invoice_repo.stats_for_user(session, user.id)
    recent = (
        await session.execute(
            select(Invoice)
            .where(Invoice.user_id == user.id)
            .order_by(desc(Invoice.created_at))
            .limit(6)
        )
    ).scalars().all()

    review_q = (
        select(Invoice)
        .where(Invoice.user_id == user.id, Invoice.status == "estimating")
        .order_by(desc(Invoice.created_at))
        .limit(3)
    )
    in_review = (await session.execute(review_q)).scalars().all()

    top_refs_q = (
        select(ReferenceProject)
        .where(ReferenceProject.is_active.is_(True))
        .order_by(desc(ReferenceProject.imported_at))
        .limit(3)
    )
    top_refs = (await session.execute(top_refs_q)).scalars().all()

    now = datetime.now(timezone.utc)
    month_word = _RU_MONTH_NOM[now.month - 1]

    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "request": request,
            "user": user,
            "stats": stats,
            "recent": recent,
            "in_review": in_review,
            "top_refs": top_refs,
            "month_word": month_word,
        },
    )
