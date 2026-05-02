"""Конфигурация приложения из переменных окружения (ТЗ v2)."""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    BOT_TOKEN: str = Field(default="")
    ADMIN_IDS: str = Field(default="")

    ANTHROPIC_API_KEY: str = Field(default="")
    # Пусто = использовать дефолт SDK (api.anthropic.com).
    # Через прокси (например ProxyAPI) — задать в .env: ANTHROPIC_BASE_URL=https://api.proxyapi.ru/anthropic/
    ANTHROPIC_BASE_URL: str = Field(default="")
    PRIMARY_MODEL: str = Field(default="claude-sonnet-4-6")
    FALLBACK_MODEL: str = Field(default="claude-opus-4-6")

    OPENAI_API_KEY: str = Field(default="")
    OPENAI_BASE_URL: str = Field(default="")
    EMBEDDINGS_MODEL: str = Field(default="text-embedding-3-small")

    HIGH_CONFIDENCE_THRESHOLD: float = Field(default=0.85, ge=0.0, le=1.0)
    MEDIUM_CONFIDENCE_THRESHOLD: float = Field(default=0.6, ge=0.0, le=1.0)
    TOP_K_REFERENCES: int = Field(default=5, ge=1, le=20)

    DATABASE_URL: str = Field(default="sqlite+aiosqlite:///./data/smeta_bot.db")
    LOG_LEVEL: str = Field(default="INFO")
    LOG_FILE: str = Field(default="./logs/bot.log")

    COMPANY_NAME: str = Field(default="ООО ВИЛИНС")
    COMPANY_INN: str = Field(default="7714356598")
    COMPANY_KPP: str = Field(default="504701001")
    COMPANY_ADDRESS: str = Field(default="")
    COMPANY_PHONE: str = Field(default="+7 (495) 275-40-01")
    COMPANY_WEB: str = Field(default="WWW.VILINS.COM")
    EXECUTOR_NAME: str = Field(default="Алексей")
    EXECUTOR_PHONE: str = Field(default="8 999 916 04 24")

    # Web
    WEB_SECRET_KEY: str = Field(default="change-me-in-production-please")
    WEB_SESSION_MAX_AGE: int = Field(default=60 * 60 * 24 * 14)  # 14 дней
    WEB_HOST: str = Field(default="127.0.0.1")
    WEB_PORT: int = Field(default=8000)

    @field_validator("ADMIN_IDS", mode="before")
    @classmethod
    def strip_admin_ids(cls, v: str | list[int] | int) -> str:
        if isinstance(v, list):
            return ",".join(str(x) for x in v)
        if isinstance(v, int):
            return str(v)
        return (v or "").strip()

    @property
    def admin_id_list(self) -> list[int]:
        if not self.ADMIN_IDS:
            return []
        out: list[int] = []
        for part in self.ADMIN_IDS.split(","):
            part = part.strip()
            if part.isdigit():
                out.append(int(part))
        return out


@lru_cache
def get_config() -> Config:
    return Config()


config = get_config()
