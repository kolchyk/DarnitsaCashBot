from dataclasses import dataclass

from libs.common import AppSettings, get_settings


@dataclass(slots=True)
class BotConfig:
    token: str
    webhook_url: str | None
    admin_ids: list[int]
    max_receipts_per_day: int = 3

    @classmethod
    def from_settings(cls, settings: AppSettings | None = None) -> "BotConfig":
        settings = settings or get_settings()
        return cls(
            token=settings.telegram_bot_token,
            webhook_url=settings.telegram_webhook_url,
            admin_ids=settings.telegram_admin_id_list,
        )

