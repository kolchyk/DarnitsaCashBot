from __future__ import annotations

from typing import Iterable


def is_receipt_eligible(catalog_aliases: dict[str, list[str]], line_items: Iterable[dict]) -> bool:
    for item in line_items:
        name = item.get("name", "").lower()
        for alias_list in catalog_aliases.values():
            if any(alias in name for alias in alias_list):
                return True
    return False

