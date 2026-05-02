#!/usr/bin/env python3
"""Лёгкие проверки импорта без сети и без BOT_TOKEN."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    import bot.router  # noqa: F401
    from bot.handlers import admin, confirm, estimation, manual, start, upload  # noqa: F401
    from config import config  # noqa: F401
    from core.estimator.price_estimator import PriceEstimator  # noqa: F401
    from core.pdf.generator import PDFGenerator  # noqa: F401
    from core.reference_db import importer, retriever  # noqa: F401
    from db import models  # noqa: F401
    from db import invoice_repo, reference_repo  # noqa: F401

    _ = config.DATABASE_URL
    print("smoke_checks: OK")


if __name__ == "__main__":
    main()
