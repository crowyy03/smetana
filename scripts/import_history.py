#!/usr/bin/env python3
"""Импорт исторических КП из data/reference_kp/ в БД прецедентов."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from loguru import logger

from db.database import AsyncSessionLocal, init_db
from core.reference_db.importer import import_single_kp_file


async def main_async(*, force: bool, only: str | None) -> None:
    await init_db()
    kp_dir = ROOT / "data" / "reference_kp"
    extracted = ROOT / "data" / "extracted"
    kp_dir.mkdir(parents=True, exist_ok=True)
    extracted.mkdir(parents=True, exist_ok=True)

    exts = {".pdf", ".xlsx", ".docx"}
    files = sorted([p for p in kp_dir.iterdir() if p.is_file() and p.suffix.lower() in exts])
    if only:
        needle = only
        for ext in (".pdf", ".xlsx", ".docx"):
            if needle.endswith(ext):
                needle = needle[: -len(ext)]
                break
        files = [p for p in files if needle in p.name]
    if not files:
        logger.warning("Нет файлов в {}", kp_dir)
        return

    async with AsyncSessionLocal() as session:
        for fp in files:
            try:
                await import_single_kp_file(session, fp, extracted_dir=extracted, force=force)
            except Exception as e:  # noqa: BLE001
                logger.error("Failed {}: {}", fp.name, e)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="Переимпорт при совпадении content_hash")
    ap.add_argument("--only", type=str, default=None, help="Фильтр по имени/slug файла")
    args = ap.parse_args()
    asyncio.run(main_async(force=args.force, only=args.only))


if __name__ == "__main__":
    main()
