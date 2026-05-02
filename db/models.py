"""SQLAlchemy 2.0 модели (ТЗ v2: прецеденты + сметы)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

if TYPE_CHECKING:
    pass


class Base(DeclarativeBase):
    pass


class ReferenceProject(Base):
    """Историческое КП — прецедент."""

    __tablename__ = "reference_projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_file: Mapped[str] = mapped_column(String(512), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    project_name: Mapped[str] = mapped_column(String(512), default="")
    client_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    object_type: Mapped[str] = mapped_column(String(64), default="other")
    project_date: Mapped[date] = mapped_column(Date, nullable=False)

    total_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0"))
    items_count: Mapped[int] = mapped_column(Integer, default=0)
    raw_content: Mapped[str] = mapped_column(Text, default="")

    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    items: Mapped[list["ReferenceItem"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="ReferenceItem.id"
    )


class ReferenceItem(Base):
    """Позиция из исторического КП."""

    __tablename__ = "reference_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("reference_projects.id", ondelete="CASCADE"), nullable=False)

    name: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    material: Mapped[str | None] = mapped_column(String(512), nullable=True)
    coating: Mapped[str | None] = mapped_column(String(512), nullable=True)
    size_text: Mapped[str | None] = mapped_column(String(256), nullable=True)
    mounting: Mapped[str | None] = mapped_column(String(256), nullable=True)
    category: Mapped[str] = mapped_column(String(64), default="other")

    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=Decimal("1"))
    unit: Mapped[str] = mapped_column(String(32), default="шт.")
    unit_price: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    total_price: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    section: Mapped[int] = mapped_column(Integer, default=1)

    search_text: Mapped[str] = mapped_column(Text, default="")
    embedding: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    project: Mapped["ReferenceProject"] = relationship(back_populates="items")


class User(Base):
    """Пользователь веб-интерфейса."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), default="")
    role: Mapped[str] = mapped_column(String(32), default="estimator")
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    theme_pref: Mapped[str] = mapped_column(String(16), default="system")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Invoice(Base):
    """Сгенерированная смета."""

    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_number: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    client_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    object_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    object_type: Mapped[str | None] = mapped_column(String(64), nullable=True)

    status: Mapped[str] = mapped_column(String(32), default="draft")

    total_section1: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0"))
    total_section2: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0"))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0"))

    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    telegram_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_via: Mapped[str] = mapped_column(String(16), default="bot")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pdf_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    source_file_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_format: Mapped[str] = mapped_column(String(32), default="text")

    items: Mapped[list["InvoiceItem"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan", order_by="InvoiceItem.sort_order"
    )


class InvoiceItem(Base):
    """Позиция в смете."""

    __tablename__ = "invoice_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    original_text: Mapped[str] = mapped_column(Text, default="")
    name: Mapped[str] = mapped_column(String(512), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=Decimal("1"))
    unit: Mapped[str] = mapped_column(String(32), default="шт.")
    unit_price: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0"))
    total_price: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0"))
    section: Mapped[int] = mapped_column(Integer, default=1)

    estimation_method: Mapped[str] = mapped_column(String(32), default="needs_manual")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    reference_item_ids: Mapped[str] = mapped_column(Text, default="[]")
    estimation_reasoning: Mapped[str] = mapped_column(Text, default="")

    was_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    was_modified: Mapped[bool] = mapped_column(Boolean, default=False)
    original_suggested_unit_price: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)

    invoice: Mapped["Invoice"] = relationship(back_populates="items")


class EstimationLog(Base):
    """Лог оценки позиции."""

    __tablename__ = "estimation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_item_id: Mapped[int] = mapped_column(ForeignKey("invoice_items.id", ondelete="CASCADE"), nullable=False)

    request_text: Mapped[str] = mapped_column(Text, default="")
    references_used: Mapped[str] = mapped_column(Text, default="[]")
    llm_response: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    final_price: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal("0"))
    was_overridden: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
