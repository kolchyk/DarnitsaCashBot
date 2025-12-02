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


def _contains_as_word_part(text: str, keywords: Iterable[str]) -> bool:
    """
    Check if text contains any keyword as a word part (after number, dash, or at start of product name).
    
    This handles cases like:
    - "№ 13204 Каптопрес-Дарниця" -> finds "Дарниця" after dash (in compound name)
    - "Каптопрес-Дарниця" -> finds "Дарниця" after dash
    - "13204 Дарниця" -> finds "Дарниця" after number
    - "№ 13204 Дарниця" -> finds "Дарниця" after number
    
    Does NOT match:
    - "Pharma Darnitsa Citramon" -> "Darnitsa" is in the middle, not a prefix
    """
    if not text:
        return False
    
    for keyword in keywords:
        if not keyword:
            continue
        keyword_lower = keyword.lower()
        
        # Check if keyword appears in text
        idx = text.lower().find(keyword_lower)
        if idx == -1:
            continue
        
        # Check if it's at the start (handled by _starts_with_any)
        if idx == 0:
            continue
        
        prev_char = text[idx - 1]
        
        # Only match if keyword is after:
        # 1. Dash (compound name like "Каптопрес-Дарниця")
        # 2. Number or № (product code like "№ 13204 Дарниця" or "13204 Дарниця")
        # 3. Space, but only if before space there's a number, №, or dash
        
        if prev_char == '-':
            # After dash - always valid (compound name)
            next_idx = idx + len(keyword_lower)
            if next_idx >= len(text) or not text[next_idx].isalpha():
                return True
        elif prev_char.isdigit() or prev_char == '№':
            # After number or № - valid (product code)
            next_idx = idx + len(keyword_lower)
            if next_idx >= len(text) or not text[next_idx].isalpha():
                return True
        elif prev_char == ' ':
            # After space - valid if:
            # 1. Before space there's number, №, or dash
            # 2. Before space there's a word (for compound names like "Каптопрес Дарниця")
            #    but only if word is long enough (>3 chars) to avoid false positives like "от Дарниця"
            before_space_idx = idx - 2
            if before_space_idx >= 0:
                char_before_space = text[before_space_idx]
                if char_before_space.isdigit() or char_before_space == '№' or char_before_space == '-':
                    # Valid: "№ 13204 Дарниця", "13204 Дарниця", "Каптопрес- Дарниця"
                    next_idx = idx + len(keyword_lower)
                    if next_idx >= len(text) or not text[next_idx].isalpha():
                        return True
                elif char_before_space.isalpha():
                    # Check if there's a word before space (for "Каптопрес Дарниця")
                    # Find start of word before space
                    word_start = before_space_idx
                    while word_start > 0 and (text[word_start].isalpha() or text[word_start] == '-'):
                        word_start -= 1
                    if text[word_start] in (' ', '-', '№') or text[word_start].isdigit() or word_start == 0:
                        word_start += 1
                    word_before = text[word_start:before_space_idx + 1]
                    word_length = len(word_before)
                    
                    # Only accept if:
                    # 1. Word is long enough (>4 chars) to be part of compound name
                    # 2. Word contains Cyrillic characters (Ukrainian/Russian names)
                    #    OR word ends with consonant typical for drug names
                    has_cyrillic = any('\u0400' <= c <= '\u04FF' for c in word_before)
                    ends_with_consonant = word_before and word_before[-1].lower() in 'бвгджзклмнпрстфхцчшщ'
                    
                    if word_length > 4 and (has_cyrillic or ends_with_consonant):
                        next_idx = idx + len(keyword_lower)
                        if next_idx >= len(text) or not text[next_idx].isalpha():
                            return True
    
    return False


def has_darnitsa_prefix(text: str | None) -> bool:
    """
    Return True when the provided text contains a Darnitsa keyword as a prefix or word part.

    Handles Cyrillic + transliterated Latin variants and tolerates separators like
    spaces, dashes, commas right after the prefix. Also finds "Дарниця" after numbers
    or other prefixes (e.g., "№ 13204 Каптопрес-Дарниця").
    """
    normalized = _normalize_source(text).lower()
    transliterated = unidecode(normalized)
    
    # Check if starts with prefix (original behavior)
    if _starts_with_any(normalized, (kw.lower() for kw in DARNITSA_KEYWORDS_CYRILLIC)):
        return True
    if _starts_with_any(transliterated, (kw.lower() for kw in DARNITSA_KEYWORDS_LATIN)):
        return True
    
    # Check if contains as word part (for cases like "№ 13204 Каптопрес-Дарниця")
    if _contains_as_word_part(normalized, (kw.lower() for kw in DARNITSA_KEYWORDS_CYRILLIC)):
        return True
    if _contains_as_word_part(transliterated, (kw.lower() for kw in DARNITSA_KEYWORDS_LATIN)):
        return True
    
    return False

