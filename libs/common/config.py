from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse
import os

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Centralised configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=("env.example", ".env"), env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["local", "dev", "prod"] = "local"
    log_level: str = "INFO"

    telegram_bot_token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")
    telegram_webhook_url: str | None = Field(default=None, alias="TELEGRAM_WEBHOOK_URL")
    telegram_admin_ids: str = Field(default="", alias="TELEGRAM_ADMIN_IDS")
    api_gateway_url: str = Field(default="http://localhost:8000", alias="API_GATEWAY_URL")

    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="darnitsa_cashbot", alias="POSTGRES_DB")
    postgres_user: str = Field(default="darnitsa", alias="POSTGRES_USER")
    postgres_password: str = Field(default="darnitsa", alias="POSTGRES_PASSWORD")
    postgres_ssl_mode: str = Field(default="prefer", alias="POSTGRES_SSL_MODE")
    
    @model_validator(mode="after")
    def parse_heroku_urls(self):
        """Parse Heroku DATABASE_URL if provided."""
        # Parse DATABASE_URL
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            parsed = urlparse(db_url)
            self.postgres_user = parsed.username or self.postgres_user
            self.postgres_password = parsed.password or self.postgres_password
            self.postgres_host = parsed.hostname or self.postgres_host
            self.postgres_port = parsed.port or self.postgres_port
            self.postgres_db = parsed.path.lstrip("/") if parsed.path else self.postgres_db
        
        return self

    # Local file storage configuration (no MinIO/S3 needed for MVP)
    storage_base_dir: str = Field(default="storage", alias="STORAGE_BASE_DIR")

    easypay_api_base: str = Field(default="http://localhost:8080", alias="EASYPAY_API_BASE")
    easypay_merchant_id: str = Field(default="merchant", alias="EASYPAY_MERCHANT_ID")
    easypay_merchant_secret: str = Field(default="secret", alias="EASYPAY_MERCHANT_SECRET")

    portmone_api_base: str = Field(
        default="https://direct.portmone.com.ua/api/directcash/",
        alias="PORTMONE_API_BASE",
    )
    portmone_login: str = Field(default="demo_login", alias="PORTMONE_LOGIN")
    portmone_password: str = Field(default="demo_password", alias="PORTMONE_PASSWORD")
    portmone_version: str = Field(default="2", alias="PORTMONE_VERSION")
    portmone_lang: str | None = Field(default=None, alias="PORTMONE_LANG")
    portmone_cert_path: Path | None = Field(default=None, alias="PORTMONE_CERT_PATH")
    portmone_key_path: Path | None = Field(default=None, alias="PORTMONE_KEY_PATH")
    portmone_payee_id: str = Field(default="100000", alias="PORTMONE_PAYEE_ID")
    portmone_payee_id_kyivstar: str | None = Field(default=None, alias="PORTMONE_PAYEE_ID_KYIVSTAR")
    portmone_payee_id_vodafone: str | None = Field(default=None, alias="PORTMONE_PAYEE_ID_VODAFONE")
    portmone_payee_id_lifecell: str | None = Field(default=None, alias="PORTMONE_PAYEE_ID_LIFECELL")
    portmone_default_currency: str = Field(default="UAH", alias="PORTMONE_DEFAULT_CURRENCY")
    portmone_webhook_token: str | None = Field(default=None, alias="PORTMONE_WEBHOOK_TOKEN")

    encryption_secret: str = Field(..., alias="ENCRYPTION_SECRET")
    jwt_secret: str = Field(default="jwt-secret", alias="JWT_SECRET")
    jwt_alg: str = Field(default="HS256", alias="JWT_ALG")

    tesseract_cmd: str | None = Field(default=None, alias="TESSERACT_CMD")
    tessdata_dir: str | None = Field(default=None, alias="TESSDATA_DIR")
    ocr_languages: str = Field(default="ukr+eng", alias="OCR_LANGUAGES")
    ocr_auto_accept_threshold: float = Field(default=0.8, alias="OCR_AUTO_ACCEPT_THRESHOLD")
    ocr_manual_review_threshold: float = Field(default=0.4, alias="OCR_MANUAL_REVIEW_THRESHOLD")
    ocr_totals_tolerance_percent: float = Field(default=1.0, alias="OCR_TOTALS_TOLERANCE_PERCENT")
    ocr_storage_prefix: str = Field(default="ocr-artifacts", alias="OCR_STORAGE_PREFIX")
    ocr_artifact_ttl_days: int = Field(default=90, alias="OCR_ARTIFACT_TTL_DAYS")
    ocr_save_preprocessed: bool = Field(default=True, alias="OCR_SAVE_PREPROCESSED")
    ocr_vendor_fallback_enabled: bool = Field(default=False, alias="OCR_VENDOR_FALLBACK_ENABLED")

    @property
    def database_url(self) -> str:
        """Get database URL, preferring Heroku DATABASE_URL if available."""
        # Check if DATABASE_URL is set in environment (Heroku)
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            # Convert postgres:// to postgresql+asyncpg:// for SQLAlchemy
            return db_url.replace("postgres://", "postgresql+asyncpg://", 1)
        # Build URL from components
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

