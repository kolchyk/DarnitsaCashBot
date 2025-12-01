from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Centralised configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=(".env", "env.example"), env_file_encoding="utf-8")

    app_env: Literal["local", "dev", "prod"] = "local"
    log_level: str = "INFO"

    telegram_bot_token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")
    telegram_webhook_url: str | None = Field(default=None, alias="TELEGRAM_WEBHOOK_URL")
    telegram_admin_ids: str = Field(default="", alias="TELEGRAM_ADMIN_IDS")

    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="darnitsa_cashbot", alias="POSTGRES_DB")
    postgres_user: str = Field(default="darnitsa", alias="POSTGRES_USER")
    postgres_password: str = Field(default="darnitsa", alias="POSTGRES_PASSWORD")

    storage_endpoint: str = Field(default="http://localhost:9000", alias="STORAGE_ENDPOINT")
    storage_bucket: str = Field(default="receipts", alias="STORAGE_BUCKET")
    storage_access_key: str = Field(default="miniokey", alias="STORAGE_ACCESS_KEY")
    storage_secret_key: str = Field(default="miniopass", alias="STORAGE_SECRET_KEY")

    rabbitmq_host: str = Field(default="localhost", alias="RABBITMQ_HOST")
    rabbitmq_port: int = Field(default=5672, alias="RABBITMQ_PORT")
    rabbitmq_user: str = Field(default="guest", alias="RABBITMQ_DEFAULT_USER")
    rabbitmq_password: str = Field(default="guest", alias="RABBITMQ_DEFAULT_PASS")

    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")

    easypay_api_base: str = Field(default="http://localhost:8080", alias="EASYPAY_API_BASE")
    easypay_merchant_id: str = Field(default="merchant", alias="EASYPAY_MERCHANT_ID")
    easypay_merchant_secret: str = Field(default="secret", alias="EASYPAY_MERCHANT_SECRET")

    encryption_secret: str = Field(..., alias="ENCRYPTION_SECRET")
    jwt_secret: str = Field(default="jwt-secret", alias="JWT_SECRET")
    jwt_alg: str = Field(default="HS256", alias="JWT_ALG")

    otel_endpoint: str | None = Field(default=None, alias="OTEL_EXPORTER_OTLP_ENDPOINT")
    prometheus_dir: Path | None = Field(default=None, alias="PROMETHEUS_MULTIPROC_DIR")

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def telegram_admin_id_list(self) -> list[int]:
        return [
            int(value.strip())
            for value in self.telegram_admin_ids.split(",")
            if value.strip().isdigit()
        ]


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()  # type: ignore[arg-type]

