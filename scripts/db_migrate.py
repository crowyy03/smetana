"""Идемпотентная миграция SQLite-схемы под web-интерфейс v2.

Что делает:
1. Создаёт таблицу users (через Base.metadata.create_all — идемпотентно).
2. Если таблица invoices существует со старой схемой (telegram_user_id NOT NULL,
   нет user_id / created_via), пересобирает таблицу: rename → создать новую → перелить данные → drop.
3. Если новая схема уже на месте — не трогает.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# чтобы можно было запускать из корня проекта: python scripts/db_migrate.py
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from db.database import _engine, init_db  # noqa: E402


REQUIRED_INVOICE_COLUMNS = {"user_id", "created_via"}


async def _column_info(conn, table: str) -> dict[str, dict]:
    res = await conn.execute(text(f"PRAGMA table_info({table})"))
    rows = res.fetchall()
    out: dict[str, dict] = {}
    for r in rows:
        out[r[1]] = {"type": r[2], "notnull": bool(r[3]), "dflt": r[4], "pk": bool(r[5])}
    return out


async def _table_exists(conn, table: str) -> bool:
    res = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"), {"t": table})
    return res.first() is not None


async def _rebuild_invoices(conn) -> None:
    """SQLite не умеет DROP NOT NULL — пересобираем таблицу.

    Создаёт таблицу invoices_new c новой схемой, копирует данные, дропает старую, переименовывает.
    """
    print("→ Пересобираю invoices (старая схема обнаружена)…")

    cols = await _column_info(conn, "invoices")
    has_user_id = "user_id" in cols
    has_created_via = "created_via" in cols

    await conn.execute(text("PRAGMA foreign_keys=OFF"))
    await conn.execute(text("BEGIN"))
    try:
        # создаём новую таблицу с правильной схемой (захардкожено — синхронизировано с models.py)
        await conn.execute(
            text(
                """
            CREATE TABLE invoices_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                invoice_number VARCHAR(32) NOT NULL,
                client_name VARCHAR(512),
                contact_name VARCHAR(512),
                object_name VARCHAR(512),
                object_type VARCHAR(64),
                status VARCHAR(32) NOT NULL DEFAULT 'draft',
                total_section1 NUMERIC(16, 2) NOT NULL DEFAULT 0,
                total_section2 NUMERIC(16, 2) NOT NULL DEFAULT 0,
                total_amount NUMERIC(16, 2) NOT NULL DEFAULT 0,
                telegram_user_id BIGINT,
                telegram_username VARCHAR(255),
                user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                created_via VARCHAR(16) NOT NULL DEFAULT 'bot',
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                completed_at DATETIME,
                pdf_path VARCHAR(1024),
                source_file_name VARCHAR(512),
                source_format VARCHAR(32) NOT NULL DEFAULT 'text'
            )
            """
            )
        )

        select_user_id = "user_id" if has_user_id else "NULL AS user_id"
        select_created_via = "created_via" if has_created_via else "'bot' AS created_via"

        await conn.execute(
            text(
                f"""
            INSERT INTO invoices_new (
                id, invoice_number, client_name, contact_name, object_name, object_type,
                status, total_section1, total_section2, total_amount,
                telegram_user_id, telegram_username, user_id, created_via,
                created_at, completed_at, pdf_path, source_file_name, source_format
            )
            SELECT
                id, invoice_number, client_name, contact_name, object_name, object_type,
                status, total_section1, total_section2, total_amount,
                telegram_user_id, telegram_username, {select_user_id}, {select_created_via},
                created_at, completed_at, pdf_path, source_file_name, source_format
            FROM invoices
            """
            )
        )
        await conn.execute(text("DROP TABLE invoices"))
        await conn.execute(text("ALTER TABLE invoices_new RENAME TO invoices"))
        await conn.execute(text("CREATE INDEX ix_invoices_invoice_number ON invoices (invoice_number)"))
        await conn.execute(text("CREATE INDEX ix_invoices_telegram_user_id ON invoices (telegram_user_id)"))
        await conn.execute(text("CREATE INDEX ix_invoices_user_id ON invoices (user_id)"))
        await conn.execute(text("COMMIT"))
        print("  ✓ invoices пересобрана")
    except Exception:
        await conn.execute(text("ROLLBACK"))
        raise
    finally:
        await conn.execute(text("PRAGMA foreign_keys=ON"))


async def _needs_rebuild(conn) -> bool:
    if not await _table_exists(conn, "invoices"):
        return False
    cols = await _column_info(conn, "invoices")
    if not REQUIRED_INVOICE_COLUMNS.issubset(cols.keys()):
        return True
    tg = cols.get("telegram_user_id")
    if tg and tg["notnull"]:
        return True
    return False


async def main() -> None:
    print("→ Создаю недостающие таблицы (users и др.)…")
    await init_db()

    async with _engine.begin() as conn:
        if await _needs_rebuild(conn):
            await _rebuild_invoices(conn)
        else:
            print("  ✓ invoices уже в новой схеме")

    print("Готово.")


if __name__ == "__main__":
    asyncio.run(main())
