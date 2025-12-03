from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import datetime
from html.parser import HTMLParser
from typing import Any

LOGGER = logging.getLogger(__name__)


class ScrapingError(Exception):
    """Raised when scraping fails."""


class SimpleHTMLParser(HTMLParser):
    """Simple HTML parser using standard library only - no BeautifulSoup needed."""
    
    def __init__(self):
        super().__init__()
        self.tables = []
        self.current_table = []
        self.current_row = []
        self.current_cell = ""
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.text_content = []
        self.current_tag = None
        
    def handle_starttag(self, tag, attrs):
        self.current_tag = tag
        if tag == "table":
            self.in_table = True
            self.current_table = []
        elif tag == "tr" and self.in_table:
            self.in_row = True
            self.current_row = []
        elif tag in ("td", "th") and self.in_row:
            self.in_cell = True
            self.current_cell = ""
            
    def handle_data(self, data):
        text = data.strip()
        if text:
            self.text_content.append(text)
        if self.in_cell:
            self.current_cell += data
            
    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.in_cell:
            self.current_row.append(self.current_cell.strip())
            self.current_cell = ""
            self.in_cell = False
        elif tag == "tr" and self.in_row:
            if self.current_row:
                self.current_table.append(self.current_row)
            self.current_row = []
            self.in_row = False
        elif tag == "table" and self.in_table:
            if self.current_table:
                self.tables.append(self.current_table)
            self.current_table = []
            self.in_table = False
        self.current_tag = None


def scrape_receipt_data(url: str) -> dict[str, Any]:
    """
    Scrape receipt data from tax.gov.ua receipt page.
    Uses Playwright for JavaScript rendering (tax.gov.ua is an Angular SPA).
    
    Args:
        url: URL to the receipt page (cabinet.tax.gov.ua/cashregs/check?id=...)
        
    Returns:
        Dictionary with receipt data in format compatible with ocr_payload
        
    Raises:
        ScrapingError: If scraping fails
    """
    LOGGER.info("Starting receipt scraping with Playwright: url=%s", url)
    
    # Run async scraping in sync context
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(_scrape_with_playwright(url))


async def _scrape_with_playwright(url: str) -> dict[str, Any]:
    """Async implementation of receipt scraping using Playwright."""
    try:
        from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
    except ImportError as e:
        LOGGER.error("Playwright not installed: %s", e)
        raise ScrapingError("Playwright not available. Install with: pip install playwright && playwright install chromium") from e
    
    html_content = ""
    
    try:
        async with async_playwright() as p:
            # Launch browser (headless mode for server)
            browser_args = [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",  # Important for Docker/Heroku
                "--disable-gpu",
                "--single-process",  # Reduce memory usage on Heroku
            ]
            
            # Check for Heroku environment
            is_heroku = bool(os.environ.get("DYNO"))
            if is_heroku:
                LOGGER.debug("Running on Heroku, using optimized settings")
            
            browser = await p.chromium.launch(
                headless=True,
                args=browser_args,
            )
            
            try:
                # Create new page with timeout
                page = await browser.new_page()
                page.set_default_timeout(30000)  # 30 seconds
                
                LOGGER.debug("Navigating to URL: %s", url)
                
                # Navigate to page
                await page.goto(url, wait_until="networkidle")
                
                # Wait for receipt content to load
                # The Angular app renders into <app-root>
                # Wait for specific content indicators
                try:
                    # Wait for any of these selectors that indicate content loaded
                    await page.wait_for_selector(
                        "table, .receipt-items, .check-items, .product-list, [class*='item'], [class*='product']",
                        timeout=15000
                    )
                    LOGGER.debug("Content selector found, page loaded")
                except PlaywrightTimeout:
                    LOGGER.warning("Timeout waiting for content selector, proceeding anyway")
                
                # Additional wait for dynamic content
                await page.wait_for_timeout(2000)
                
                # Get rendered HTML
                html_content = await page.content()
                LOGGER.debug("Got rendered HTML: %d characters", len(html_content))
                
                # Debug: log first part of HTML
                LOGGER.debug("HTML preview (first 500 chars): %s", html_content[:500])
                
            finally:
                await browser.close()
        
        # Parse rendered HTML
        return _parse_rendered_html(html_content, url)
        
    except PlaywrightTimeout as e:
        LOGGER.error("Playwright timeout: %s", e)
        raise ScrapingError(f"Timeout loading receipt page: {str(e)}") from e
    except Exception as e:
        LOGGER.error("Error scraping receipt with Playwright: %s", e, exc_info=True)
        raise ScrapingError(f"Failed to scrape receipt data: {str(e)}") from e


def _parse_rendered_html(html_content: str, url: str) -> dict[str, Any]:
    """Parse the rendered HTML and extract receipt data."""
    
    # Parse HTML with standard library parser
    parser = SimpleHTMLParser()
    parser.feed(html_content)
    page_text = " ".join(parser.text_content)
    
    LOGGER.debug("Parsed HTML: %d tables, %d text segments", len(parser.tables), len(parser.text_content))
    LOGGER.debug("Page text preview: %s", page_text[:500] if page_text else "(empty)")
    
    # Extract merchant name
    merchant = _extract_merchant(page_text, html_content)
    LOGGER.debug("Extracted merchant: %s", merchant)
    
    # Extract purchase timestamp
    purchase_ts = _extract_purchase_timestamp(page_text, url)
    LOGGER.debug("Extracted purchase timestamp: %s", purchase_ts)
    
    # Extract line items from tables
    line_items = _extract_line_items(parser.tables, page_text)
    LOGGER.info("Extracted %d line items", len(line_items))
    
    # Extract total (try from URL first for tax.gov.ua)
    total = _extract_total_from_url(url)
    if total is None:
        total = _extract_total(page_text, line_items)
    LOGGER.debug("Extracted total: %s", total)
    
    # Calculate confidence (scraped data is 100% accurate)
    line_confidences = [item.get("confidence", 1.0) for item in line_items]
    mean_confidence = float(sum(line_confidences) / len(line_confidences)) if line_confidences else 1.0
    
    # Build payload
    payload = {
        "merchant": merchant,
        "purchase_ts": purchase_ts.isoformat() if purchase_ts else None,
        "total": total,
        "line_items": [
            {
                "name": item["name"],
                "original_name": item.get("original_name", item["name"]),
                "normalized_name": item.get("normalized_name"),
                "quantity": item["quantity"],
                "price": item["price"],
                "confidence": item.get("confidence", 1.0),
                "sku_code": item.get("sku_code"),
                "sku_match_score": item.get("sku_match_score", 0.0),
                "is_darnitsa": item.get("is_darnitsa", False),
            }
            for item in line_items
        ],
        "confidence": {
            "mean": mean_confidence,
            "min": min(line_confidences) if line_confidences else 1.0,
            "max": max(line_confidences) if line_confidences else 1.0,
            "token_count": len(line_items),
            "auto_accept_candidate": True,  # Scraped data is reliable
        },
        "manual_review_required": False,
        "anomalies": [],
    }
    
    LOGGER.info(
        "Scraping completed: merchant=%s, line_items=%d, total=%s",
        merchant,
        len(line_items),
        total,
    )
    
    return payload


def _extract_total_from_url(url: str) -> int | None:
    """Extract total amount from URL parameters (sm=XX.XX in tax.gov.ua URLs)."""
    match = re.search(r"[?&]sm=(\d+[.,]?\d*)", url)
    if match:
        try:
            total_str = match.group(1).replace(",", ".")
            return int(float(total_str) * 100)  # Convert to kopecks
        except ValueError:
            pass
    return None


def _extract_merchant(page_text: str, html_content: str) -> str | None:
    """Extract merchant name from the receipt page using regex patterns."""
    # Try to find merchant name in common patterns
    patterns = [
        r'<h1[^>]*>(.*?)</h1>',
        r'class=["\']merchant["\'][^>]*>(.*?)<',
        r'class=["\']store-name["\'][^>]*>(.*?)<',
        r'class=["\']company-name["\'][^>]*>(.*?)<',
        r'class=["\'][^"\']*seller[^"\']*["\'][^>]*>(.*?)<',
        r'<title>(.*?)</title>',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)
        if match:
            text = re.sub(r'<[^>]+>', '', match.group(1)).strip()
            if text and len(text) > 3 and text != "Електронний кабінет платника":
                return text
    
    # Try to find in text content with keywords
    keywords = ["пн", "єдрпоу", "торговець", "продавець", "магазин", "компанія", "тов ", "фоп "]
    lines = page_text.split()
    
    # Look for company identifiers
    for i, word in enumerate(lines):
        word_lower = word.lower()
        if any(kw in word_lower for kw in keywords):
            # Try to get next few words as company name
            if i + 1 < len(lines):
                potential_name = " ".join(lines[i:min(i+5, len(lines))])
                if len(potential_name) > 5:
                    return potential_name[:100]  # Limit length
    
    return None


def _parse_datetime(dt_str: str) -> datetime | None:
    """Parse datetime string in various formats using standard library."""
    # Common datetime formats to try
    formats = [
        "%Y-%m-%d %H:%M",           # 2024-12-01 14:30
        "%Y-%m-%d %H:%M:%S",        # 2024-12-01 14:30:45
        "%d.%m.%Y %H:%M",           # 01.12.2024 14:30
        "%d.%m.%Y %H:%M:%S",        # 01.12.2024 14:30:45
        "%d/%m/%Y %H:%M",           # 01/12/2024 14:30
        "%d/%m/%Y %H:%M:%S",        # 01/12/2024 14:30:45
        "%d-%m-%Y %H:%M",           # 01-12-2024 14:30
        "%d-%m-%Y %H:%M:%S",        # 01-12-2024 14:30:45
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue
    
    # Try ISO format as last resort
    try:
        return datetime.fromisoformat(dt_str.replace(" ", "T"))
    except (ValueError, AttributeError):
        pass
    
    return None


def _extract_purchase_timestamp(page_text: str, url: str) -> datetime | None:
    """Extract purchase timestamp from the receipt page or URL."""
    # Try to extract from URL parameters first (tax.gov.ua format)
    date_match = re.search(r"date=(\d{8})", url)
    time_match = re.search(r"time=(\d{2}):(\d{2})", url)
    
    if date_match and time_match:
        date_str = date_match.group(1)
        time_str = f"{time_match.group(1)}:{time_match.group(2)}"
        try:
            # Format: YYYYMMDD HH:MM -> YYYY-MM-DD HH:MM
            dt_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]} {time_str}"
            return _parse_datetime(dt_str)
        except Exception:
            pass
    
    # Try to find date/time in page content
    date_patterns = [
        r"(\d{2}[./-]\d{2}[./-]\d{4})\s+(\d{2}:\d{2}(?::\d{2})?)",
        r"(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}(?::\d{2})?)",
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, page_text)
        if match:
            try:
                dt_str = f"{match.group(1)} {match.group(2)}"
                parsed = _parse_datetime(dt_str)
                if parsed:
                    return parsed
            except Exception:
                continue
    
    return None


def _extract_line_items(tables: list[list[list[str]]], page_text: str) -> list[dict[str, Any]]:
    """Extract line items from parsed tables or page text."""
    line_items = []
    
    # Try to extract from tables first
    for table in tables:
        if len(table) < 2:  # Need at least header + data rows
            continue
        
        # Skip header row and process data rows
        for row in table[1:]:
            if len(row) < 2:
                continue
            
            item_data = _parse_item_row(row)
            if item_data:
                line_items.append(item_data)
    
    # If no items found in tables, try regex patterns on text
    if not line_items:
        line_items = _extract_items_from_text(page_text)
    
    return line_items


def _extract_items_from_text(page_text: str) -> list[dict[str, Any]]:
    """Extract line items from page text using regex patterns."""
    line_items = []
    
    # Pattern for items like "Product Name 2 x 50.00" or "2 x 50.00 Product Name"
    patterns = [
        # Name qty x price format
        r"([А-Яа-яІіЇїЄєҐґA-Za-z][А-Яа-яІіЇїЄєҐґA-Za-z0-9\s\-\.]+?)\s+(\d+(?:[.,]\d+)?)\s*[xх×]\s*(\d+[.,]\d+)",
        # Name price format (qty=1)
        r"([А-Яа-яІіЇїЄєҐґA-Za-z][А-Яа-яІіЇїЄєҐґA-Za-z0-9\s\-\.]+?)\s+(\d+[.,]\d+)\s*(?:грн|₴|UAH)?(?:\s|$)",
    ]
    
    for pattern in patterns:
        matches = re.finditer(pattern, page_text, re.IGNORECASE)
        for match in matches:
            try:
                if len(match.groups()) == 3:
                    # Name, qty, price pattern
                    name = match.group(1).strip()
                    quantity = int(float(match.group(2).replace(",", ".")))
                    price_str = match.group(3).replace(",", ".")
                    price = int(float(price_str) * 100)
                else:
                    # Name, price pattern (qty=1)
                    name = match.group(1).strip()
                    quantity = 1
                    price_str = match.group(2).replace(",", ".")
                    price = int(float(price_str) * 100)
                
                # Skip if name looks like a total or header
                skip_keywords = ["всього", "итого", "total", "сума", "пдв", "знижка", "разом"]
                if any(kw in name.lower() for kw in skip_keywords):
                    continue
                
                # Skip very short names
                if len(name) < 3:
                    continue
                
                line_items.append({
                    "name": name,
                    "quantity": quantity,
                    "price": price,
                    "confidence": 1.0,
                })
            except (ValueError, IndexError):
                continue
    
    return line_items


def _parse_item_row(cells: list[str]) -> dict[str, Any] | None:
    """Parse a table row into an item dictionary."""
    if len(cells) < 2:
        return None
    
    # Find name (usually first column with text)
    name = None
    quantity = 1
    price = None
    
    for text in cells:
        if not text:
            continue
        
        # Check if it's a number (price or quantity)
        price_match = re.search(r"(\d+[.,]\d+)", text)
        qty_match = re.search(r"^(\d+)$", text)
        
        if name is None and not price_match and not qty_match:
            name = text.strip()
        elif price_match and price is None:
            price_str = price_match.group(1).replace(",", ".")
            try:
                price = int(float(price_str) * 100)
            except ValueError:
                pass
        elif qty_match and quantity == 1:
            try:
                quantity = int(qty_match.group(1))
            except ValueError:
                pass
    
    if name and price is not None:
        return {
            "name": name,
            "quantity": quantity,
            "price": price,
            "confidence": 1.0,
        }
    
    return None


def _extract_total(page_text: str, line_items: list[dict[str, Any]]) -> int | None:
    """Extract total amount from the receipt page."""
    # Try to find total in page
    total_keywords = ["всього", "итого", "total", "сума", "sum", "разом", "до сплати"]
    
    for keyword in total_keywords:
        pattern = rf"{keyword}[:\s]+(\d+[.,]\d+)"
        match = re.search(pattern, page_text, re.IGNORECASE)
        if match:
            total_str = match.group(1).replace(",", ".")
            try:
                return int(float(total_str) * 100)
            except ValueError:
                continue
    
    # Calculate from line items if not found
    if line_items:
        calculated_total = sum(item.get("price", 0) * item.get("quantity", 1) for item in line_items)
        if calculated_total > 0:
            return calculated_total
    
    return None
