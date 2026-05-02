#!/usr/bin/env python3
"""Показать top-K прецедентов для текстового запроса (без LLM).

Запуск:
    python scripts/debug_retriever.py "Табличка этажная 220x220 нерж AISI 304"
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import config  # noqa: E402
from db.database import AsyncSessionLocal, init_db  # noqa: E402
from core.reference_db.retriever import ReferenceRetriever  # noqa: E402


async def main(query: str) -> None:
    await init_db()
    async with AsyncSessionLocal() as session:
        r = ReferenceRetriever()
        await r.load_index(session)
        results = await r.find_similar(session, query, top_k=config.TOP_K_REFERENCES)
        print(f"Запрос: {query}\n")
        print(f"top-{len(results)} прецедентов:\n")
        for i, (item, score) in enumerate(results, 1):
            pname = item.project.project_name if item.project else "?"
            sz = f" [{item.size_text}]" if item.size_text else ""
            mat = f" mat={item.material!r}" if item.material else ""
            print(
                f"{i:2d}. score={score:.3f}  {pname:30s}  "
                f"{item.name[:50]}{sz}  {item.unit_price} {item.unit}{mat}"
            )


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "Табличка этажная 220x220 нерж AISI 304 нитрид брауну"
    asyncio.run(main(q))
