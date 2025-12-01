from __future__ import annotations

import gettext
from functools import lru_cache
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LOCALES_PATH = BASE_DIR / "apps" / "telegram_bot" / "locales"


@lru_cache(maxsize=16)
def get_translator(locale: str):
    try:
        translation = gettext.translation("bot", localedir=str(LOCALES_PATH), languages=[locale])
    except FileNotFoundError:
        translation = gettext.translation("bot", localedir=str(LOCALES_PATH), languages=["uk"], fallback=True)
    return translation.gettext


def translate_status(_, status: str) -> str:
    """Translate receipt status to Ukrainian."""
    if not status or status == "-":
        return status
    return _(status)

