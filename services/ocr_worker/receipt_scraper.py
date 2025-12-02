from __future__ import annotations

import logging
import re
from datetime import datetime
from html.parser import HTMLParser
from typing import Any

import httpx
from pendulum import parse as parse_datetime

# Optional import for JavaScript rendering
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

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
    Uses only standard library html.parser - no BeautifulSoup needed.
    
    Args:
        url: URL to the receipt page (cabinet.tax.gov.ua/cashregs/check?id=...)
        
    Returns:
        Dictionary with receipt data in format compatible with ocr_payload
        
    Raises:
        ScrapingError: If scraping fails
    """
    LOGGER.info("Starting receipt scraping: url=%s", url)
    
    try:
        # Try to fetch with JavaScript rendering first (for Angular apps)
        html_content = None
        if PLAYWRIGHT_AVAILABLE:
            try:
                html_content = _fetch_with_playwright(url)
                LOGGER.debug("Page fetched with Playwright: content_length=%d", len(html_content) if html_content else 0)
            except Exception as e:
                LOGGER.debug("Playwright fetch failed, falling back to httpx: %s", e)
        
        # Fallback to simple HTTP request
        if not html_content:
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                response = client.get(url)
                response.raise_for_status()
                html_content = response.text
                LOGGER.debug("Page fetched with httpx: status=%d, content_length=%d", response.status_code, len(html_content))
        
        # Parse HTML with standard library parser
        parser = SimpleHTMLParser()
        parser.feed(html_content)
        page_text = " ".join(parser.text_content)
        
        # Extract merchant name
        merchant = _extract_merchant(page_text, html_content)
        LOGGER.debug("Extracted merchant: %s", merchant)
        
        # Extract purchase timestamp
        purchase_ts = _extract_purchase_timestamp(page_text, url)
        LOGGER.debug("Extracted purchase timestamp: %s", purchase_ts)
        
        # Extract line items from tables
        line_items = _extract_line_items(parser.tables, page_text)
        LOGGER.info("Extracted %d line items", len(line_items))
        
        # Extract total
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
        
    except httpx.HTTPError as e:
        LOGGER.error("HTTP error while scraping: %s", e, exc_info=True)
        raise ScrapingError(f"Failed to fetch receipt page: {str(e)}") from e
    except Exception as e:
        LOGGER.error("Error scraping receipt: %s", e, exc_info=True)
        raise ScrapingError(f"Failed to scrape receipt data: {str(e)}") from e


def _extract_merchant(page_text: str, html_content: str) -> str | None:
    """Extract merchant name from the receipt page using regex patterns."""
    # Try to find merchant name in common patterns
    patterns = [
        r'<h1[^>]*>(.*?)</h1>',
        r'class=["\']merchant["\'][^>]*>(.*?)<',
        r'class=["\']store-name["\'][^>]*>(.*?)<',
        r'class=["\']company-name["\'][^>]*>(.*?)<',
        r'<title>(.*?)</title>',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)
        if match:
            text = re.sub(r'<[^>]+>', '', match.group(1)).strip()
            if text and len(text) > 3:
                return text
    
    # Try to find in text content with keywords
    lines = page_text.split('\n')
    for i, line in enumerate(lines):
        line_lower = line.lower()
        if any(keyword in line_lower for keyword in ["магазин", "торговець", "компанія", "merchant", "store"]):
            # Try next line
            if i + 1 < len(lines):
                merchant_text = lines[i + 1].strip()
                if merchant_text and len(merchant_text) > 3:
                    return merchant_text
    
    return None


def _extract_purchase_timestamp(page_text: str, url: str) -> datetime | None:
    """Extract purchase timestamp from the receipt page or URL."""
    # Try to extract from URL parameters first
    date_match = re.search(r"date=(\d{8})", url)
    time_match = re.search(r"time=(\d{2}):(\d{2})", url)
    
    if date_match and time_match:
        date_str = date_match.group(1)
        time_str = f"{time_match.group(1)}:{time_match.group(2)}"
        try:
            # Format: YYYYMMDD HH:MM
            dt_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]} {time_str}"
            return parse_datetime(dt_str)
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
                return parse_datetime(dt_str)
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
        lines = page_text.split("\n")
        for line in lines:
            line = line.strip()
            if not line or len(line) < 5:
                continue
            
            # Try to match patterns like "Product Name 2 x 50.00" or "Product Name 100.00"
            item_match = re.search(r"(.+?)\s+(\d+)\s*[xх×]\s*(\d+[.,]\d+)", line)
            if item_match:
                name = item_match.group(1).strip()
                quantity = int(item_match.group(2))
                price_str = item_match.group(3).replace(",", ".")
                price = int(float(price_str) * 100)  # Convert to kopecks
                line_items.append({
                    "name": name,
                    "quantity": quantity,
                    "price": price,
                    "confidence": 1.0,
                })
            else:
                # Try pattern without quantity: "Product Name 100.00"
                item_match = re.search(r"(.+?)\s+(\d+[.,]\d+)\s*(?:грн|₴|UAH)?", line)
                if item_match:
                    name = item_match.group(1).strip()
                    price_str = item_match.group(2).replace(",", ".")
                    price = int(float(price_str) * 100)
                    line_items.append({
                        "name": name,
                        "quantity": 1,
                        "price": price,
                        "confidence": 1.0,
                    })
    
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
    total_keywords = ["всього", "итого", "total", "сума", "sum", "разом"]
    
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


def _fetch_with_playwright(url: str) -> str | None:
    """Fetch page content using Playwright to execute JavaScript."""
    if not PLAYWRIGHT_AVAILABLE:
        return None
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)
            
            # Wait for content to load
            page.wait_for_timeout(3000)  # Wait 3 seconds for Angular to render
            
            # Try to extract data from page
            html_content = page.content()
            browser.close()
            return html_content
    except Exception as e:
        LOGGER.warning("Playwright fetch failed: %s", e)
        return None
