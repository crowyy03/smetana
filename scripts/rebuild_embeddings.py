#!/usr/bin/env python3
"""Пересчёт embeddings для ReferenceItem (NULL или --all)."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import select, update

from db.database import AsyncSessionLocal, init_db
from db.models import ReferenceItem
from core.llm.embeddings_client import EmbeddingsClient


async def run(*, all_items: bool) -> None:
    await init_db()
    async with AsyncSessionLocal() as session:
        q = select(ReferenceItem)
        if not all_items:
            q = q.where(ReferenceItem.embedding.is_(None))
        r = await session.execute(q)
        items = list(r.scalars().all())
        if not items:
            print("Nothing to update")
            return
        texts = [it.search_text[:8000] for it in items]
        ec = EmbeddingsClient()
        vecs = await ec.create_batch(texts)
        for it, vec in zip(items, vecs, strict=True):
            await session.execute(
                update(ReferenceItem).where(ReferenceItem.id == it.id).values(embedding=vec.tobytes())
            )
        await session.commit()
        print(f"Updated {len(items)} items")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="Пересчитать все позиции")
    args = ap.parse_args()
    asyncio.run(run(all_items=args.all))


if __name__ == "__main__":
    main()
