"""Интерактивное создание/обновление админа.

Запуск:
    python scripts/create_admin.py
    python scripts/create_admin.py --email me@example.com --name "Илья" --password 'secret'
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.database import AsyncSessionLocal, init_db  # noqa: E402
from db import user_repo  # noqa: E402
from web.auth import hash_password  # noqa: E402


def _prompt(label: str, *, secret: bool = False, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        if secret:
            v = getpass.getpass(f"{label}{suffix}: ")
        else:
            v = input(f"{label}{suffix}: ").strip()
        if v:
            return v
        if default is not None:
            return default


async def main() -> int:
    parser = argparse.ArgumentParser(description="Создать или обновить администратора web-интерфейса")
    parser.add_argument("--email")
    parser.add_argument("--name", default="")
    parser.add_argument("--password")
    parser.add_argument("--role", default="admin", choices=("admin", "estimator"))
    args = parser.parse_args()

    await init_db()

    email = (args.email or _prompt("E-mail")).strip().lower()
    name = args.name or _prompt("Имя", default=email.split("@")[0])
    password = args.password
    if not password:
        p1 = _prompt("Пароль (мин 8 символов)", secret=True)
        if len(p1) < 8:
            print("Пароль слишком короткий.", file=sys.stderr)
            return 2
        p2 = _prompt("Пароль ещё раз", secret=True)
        if p1 != p2:
            print("Пароли не совпадают.", file=sys.stderr)
            return 2
        password = p1

    async with AsyncSessionLocal() as session:
        existing = await user_repo.get_by_email(session, email)
        if existing:
            print(f"→ Пользователь {email} уже существует — обновляю пароль и роль.")
            await user_repo.update_password(session, existing.id, hash_password(password))
            await user_repo.update_profile(session, existing.id, full_name=name)
            from sqlalchemy import update
            from db.models import User
            await session.execute(update(User).where(User.id == existing.id).values(role=args.role, is_active=True))
            await session.commit()
            print(f"  ✓ {email} обновлён (роль: {args.role})")
        else:
            await user_repo.create_user(
                session,
                email=email,
                password_hash=hash_password(password),
                full_name=name,
                role=args.role,
            )
            print(f"  ✓ Создан {args.role}: {email}")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
