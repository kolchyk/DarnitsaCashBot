from __future__ import annotations

import logging
from typing import Any

LOGGER = logging.getLogger(__name__)


class ScrapingError(Exception):
    """Raised when scraping fails."""


def scrape_receipt_data(url: str) -> dict[str, Any]:
    """
    Scrape receipt data from tax.gov.ua receipt page.
    
    NOTE: Playwright scraping functionality has been removed.
    This function now raises ScrapingError to indicate that scraping is not available.
    
    Args:
        url: URL to the receipt page (cabinet.tax.gov.ua/cashregs/check?id=...)
        
    Returns:
        Dictionary with receipt data in format compatible with ocr_payload
        
    Raises:
        ScrapingError: Always raises this error as scraping is not available
    """
    LOGGER.warning("Receipt scraping requested but Playwright functionality has been removed: url=%s", url)
    raise ScrapingError("Receipt scraping functionality is not available. Playwright scraping has been removed.")
