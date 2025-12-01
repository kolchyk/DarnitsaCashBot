from __future__ import annotations

import gettext
from functools import lru_cache
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LOCALES_PATH = BASE_DIR / "apps" / "telegram_bot" / "locales"


@lru_cache(maxsize=16)
def get_translator(locale: str):
    # Always use Ukrainian as default to avoid showing English messages to users
    try:
        translation = gettext.translation("bot", localedir=str(LOCALES_PATH), languages=[locale, "uk"], fallback=True)
    except FileNotFoundError:
        translation = gettext.translation("bot", localedir=str(LOCALES_PATH), languages=["uk"], fallback=True)
    return translation.gettext


def translate_status(status: str) -> str:
    """Translate receipt status to Ukrainian."""
    if not status or status == "-":
        return status
    
    status_map = {
        "pending": "очікує",
        "processing": "обробляється",
        "accepted": "прийнято",
        "rejected": "відхилено",
        "payout_pending": "очікує виплати",
        "payout_success": "виплачено",
        "payout_failed": "помилка виплати",
    }
    
    return status_map.get(status, status)

