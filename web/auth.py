"""Хэширование паролей и подписанные сессионные cookie."""

from __future__ import annotations

from itsdangerous import BadSignature, URLSafeSerializer
from passlib.context import CryptContext

from config import config

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

SESSION_COOKIE_NAME = "vilins_session"
THEME_COOKIE_NAME = "vilins_theme"


def hash_password(plain: str) -> str:
    return pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_ctx.verify(plain, hashed)
    except Exception:  # noqa: BLE001
        return False


def _serializer() -> URLSafeSerializer:
    return URLSafeSerializer(config.WEB_SECRET_KEY, salt="vilins-session")


def encode_session(user_id: int) -> str:
    return _serializer().dumps({"uid": int(user_id)})


def decode_session(token: str) -> int | None:
    try:
        data = _serializer().loads(token)
        if isinstance(data, dict) and "uid" in data:
            return int(data["uid"])
    except (BadSignature, ValueError, TypeError):
        return None
    return None
