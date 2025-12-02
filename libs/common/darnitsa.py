from __future__ import annotations

import re
import unicodedata
from typing import Iterable

from unidecode import unidecode

from .constants import DARNITSA_KEYWORDS_CYRILLIC, DARNITSA_KEYWORDS_LATIN

_WORD_SEPARATOR_PATTERN = re.compile(r"\s+")


def _normalize_source(text: str | None) -> str:
    """Normalize input text for prefix matching."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFC", text)
    normalized = normalized.strip()
    normalized = _WORD_SEPARATOR_PATTERN.sub(" ", normalized)
    return normalized


def _starts_with_any(text: str, prefixes: Iterable[str]) -> bool:
    """Check whether text begins with any of the prefixes (handling separators)."""
    if not text:
        return False
    for prefix in prefixes:
        if not prefix:
            continue
        if text.startswith(prefix):
            if len(text) == len(prefix):
                return True
            next_char = text[len(prefix)]
            if not next_char.isalpha():
                return True
    return False


def has_darnitsa_prefix(text: str | None) -> bool:
    """
    Return True when the provided text starts with a Darnitsa keyword.

    Handles Cyrillic + transliterated Latin variants and tolerates separators like
    spaces, dashes, commas right after the prefix.
    """
    normalized = _normalize_source(text).lower()
    transliterated = unidecode(normalized)
    if _starts_with_any(normalized, (kw.lower() for kw in DARNITSA_KEYWORDS_CYRILLIC)):
        return True
    return _starts_with_any(transliterated, (kw.lower() for kw in DARNITSA_KEYWORDS_LATIN))

