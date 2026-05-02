"""Импорт одного исторического КП в БД."""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from core.llm.client import LLMClient, LLMParseError
from core.llm.embeddings_client import EmbeddingsClient
from core.parsers.docx_parser import DocxParser
from core.parsers.excel_parser import ExcelParser
from core.parsers.pdf_parser import PDFParser
from core.reference_db.embeddings import build_search_text_from_row
from db.reference_repo import create_reference_project_with_items, get_project_by_content_hash


EXTRACTION_SYSTEM = "Ты анализируешь коммерческое предложение ВИЛИНС. Верни ТОЛЬКО валидный JSON без markdown и без комментариев."

EXTRACTION_USER = """Извлеки ВСЕ позиции из КП в структурированный JSON по правилам ТЗ.

Для каждой позиции: name, description, material, coating, size_text, mounting,
category (navigation|door_portal|panel|stand|service|other),
quantity, unit, unit_price, total_price, section (1 или 2).

metadata: project_name, client_name, object_type, project_date (YYYY-MM-DD), invoice_number.

ТЕКСТ КП:
{kp_text}
"""


async def _extract_plain_text(path: Path) -> str:
    suf = path.suffix.lower()
    if suf == ".pdf":
        p = PDFParser()
        text, _ = await asyncio.to_thread(p._extract_sync, path)  # noqa: SLF001
        return text
    if suf in (".xlsx", ".xls"):
        ex = ExcelParser()
        _, raw, _ = await asyncio.to_thread(ex.parse_sync, path)
        return raw
    if suf == ".docx":
        d = DocxParser()
        return await asyncio.to_thread(d._extract_text_sync, path)  # noqa: SLF001
    return path.read_text(encoding="utf-8", errors="replace")


def _parse_date(s: str | None) -> date:
    if not s:
        return date.today()
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError:
        return date.today()


async def import_single_kp_file(
    session: AsyncSession,
    file_path: Path,
    *,
    extracted_dir: Path,
    force: bool = False,
) -> ReferenceProject | None:
    """
    Импорт одного файла. Идемпотентность по SHA256(raw_text).
    Если force — удалить старый проект с тем же hash (через delete в caller) или перезаписать.
    """
    plain = await _extract_plain_text(file_path)
    h = hashlib.sha256(plain.encode("utf-8")).hexdigest()
    existing = await get_project_by_content_hash(session, h)
    if existing and not force:
        logger.info("skip duplicate content_hash={} file={}", h, file_path.name)
        return existing
    if existing and force:
        from db.reference_repo import delete_project_by_hash

        await delete_project_by_hash(session, h)

    llm = LLMClient()
    try:
        data = await llm.complete_json(
            EXTRACTION_SYSTEM,
            EXTRACTION_USER.format(kp_text=plain[:200_000]),
            max_tokens=8000,
            temperature=0,
        )
    except (LLMParseError, Exception) as e:  # noqa: BLE001
        logger.error("LLM extraction failed {}: {}", file_path.name, e)
        raise

    extracted_dir.mkdir(parents=True, exist_ok=True)
    out_json = extracted_dir / f"{file_path.stem}.json"
    out_json.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    meta = data.get("metadata") or {}
    items_raw = data.get("items") or []
    rows: list[dict[str, Any]] = []
    texts: list[str] = []
    for row in items_raw:
        row = dict(row)
        row["search_text"] = build_search_text_from_row(row)
        rows.append(row)
        texts.append(row["search_text"][:8000])

    emb_client = EmbeddingsClient()
    embeddings_np = await emb_client.create_batch(texts) if texts else []
    embeddings_bytes = [e.tobytes() for e in embeddings_np]

    total = sum(Decimal(str(r.get("total_price", 0))) for r in rows)
    proj = await create_reference_project_with_items(
        session,
        source_file=file_path.name,
        content_hash=h,
        project_name=str(meta.get("project_name") or file_path.stem),
        client_name=meta.get("client_name"),
        object_type=str(meta.get("object_type") or "other"),
        project_date=_parse_date(meta.get("project_date")),
        total_amount=total,
        raw_content=plain[:500_000],
        items_data=rows,
        embeddings=embeddings_bytes,
    )
    logger.info("imported {} items={}", file_path.name, len(rows))
    return proj
