from __future__ import annotations

import logging
import re
import time
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, urlparse

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

LOGGER = logging.getLogger(__name__)


class ScrapingError(Exception):
    """Raised when scraping fails."""


def parse_receipt_text(check_text: str) -> dict[str, Any]:
    """
    Parse receipt text data from tax.gov.ua API response.
    
    Args:
        check_text: Text content of the receipt from API
        
    Returns:
        Dictionary with parsed receipt data:
        - merchant: Merchant name
        - purchase_ts: Purchase timestamp
        - total: Total amount in kopecks
        - line_items: List of line items
    """
    result = {
        "merchant": None,
        "purchase_ts": None,
        "total": None,
        "line_items": [],
    }
    
    if not check_text:
        return result
    
    lines = check_text.split('\n')
    
    # Try to extract merchant name (usually in first few lines)
    # Look for patterns like: ТОВ "НАЗВАНИЕ" or just название аптеки
    for i, line in enumerate(lines[:15]):
        line = line.strip()
        if not line:
            continue
        
        # Skip separator lines
        if line.startswith('-') or line.startswith('='):
            continue
        
        # Look for ТОВ pattern
        if 'тов' in line.lower() or 'тоо' in line.lower():
            # Extract name, removing quotes if present
            merchant_name = line.strip().strip('"').strip("'")
            # Remove ТОВ/ТОО prefix
            merchant_name = re.sub(r'^тов\s+', '', merchant_name, flags=re.IGNORECASE)
            merchant_name = re.sub(r'^тоо\s+', '', merchant_name, flags=re.IGNORECASE)
            merchant_name = merchant_name.strip().strip('"').strip("'")
            if merchant_name and len(merchant_name) > 3:
                result["merchant"] = merchant_name
                break
        
        # Look for "Аптека" or pharmacy name
        if 'аптека' in line.lower() and len(line) > 5 and len(line) < 150:
            if not any(skip in line.lower() for skip in ['чек', 'check', 'фіскальний', 'fiscal', 'рро', 'rro', 'касовий']):
                # Try to get previous line if it contains ТОВ
                if i > 0:
                    prev_line = lines[i-1].strip()
                    if 'тов' in prev_line.lower():
                        merchant_name = prev_line.strip().strip('"').strip("'")
                        merchant_name = re.sub(r'^тов\s+', '', merchant_name, flags=re.IGNORECASE)
                        merchant_name = merchant_name.strip().strip('"').strip("'")
                        if merchant_name:
                            result["merchant"] = merchant_name
                            break
                # Otherwise use current line
                if not result["merchant"]:
                    result["merchant"] = line.strip()
                    break
    
    # Try to extract date
    date_patterns = [
        r'(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}):(\d{2}):(\d{2})',  # DD.MM.YYYY HH:MM:SS
        r'(\d{2})-(\d{2})-(\d{4})\s+(\d{2}):(\d{2}):(\d{2})',  # DD-MM-YYYY HH:MM:SS
        r'(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})',  # YYYY-MM-DD HH:MM:SS
        r'(\d{2})/(\d{2})/(\d{4})\s+(\d{2}):(\d{2}):(\d{2})',  # DD/MM/YYYY HH:MM:SS
    ]
    
    for line in lines:
        for pattern in date_patterns:
            match = re.search(pattern, line)
            if match:
                try:
                    if '.' in line:
                        # DD.MM.YYYY format
                        day, month, year, hour, minute, second = match.groups()
                        dt = datetime(int(year), int(month), int(day), int(hour), int(minute), int(second))
                    elif '/' in line:
                        # DD/MM/YYYY format
                        day, month, year, hour, minute, second = match.groups()
                        dt = datetime(int(year), int(month), int(day), int(hour), int(minute), int(second))
                    elif '-' in line and len(match.group(1)) == 4:
                        # YYYY-MM-DD format
                        year, month, day, hour, minute, second = match.groups()
                        dt = datetime(int(year), int(month), int(day), int(hour), int(minute), int(second))
                    else:
                        # DD-MM-YYYY format
                        day, month, year, hour, minute, second = match.groups()
                        dt = datetime(int(year), int(month), int(day), int(hour), int(minute), int(second))
                    result["purchase_ts"] = dt.strftime("%Y-%m-%d %H:%M:%S")
                    break
                except (ValueError, IndexError):
                    continue
        if result["purchase_ts"]:
            break
    
    # Parse line items
    # Format example:
    # АРТ.№ 2009 Цитрамон-Дарниця табл. №10 Дарниця
    # 1.000         x          36.50 =                   36.50 В
    
    line_items = []
    
    # Pattern for Ukrainian receipt format: АРТ.№ or similar
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        
        line_lower = line.lower()
        
        # Check for total line
        if 'сума до сплати' in line_lower or 'сума' in line_lower:
            total_match = re.search(r'(\d+[,.]?\d*)', line)
            if total_match:
                total_str = total_match.group(1).replace(',', '.')
                try:
                    total_uah = float(total_str)
                    result["total"] = int(total_uah * 100)
                except ValueError:
                    pass
        
        # Look for item start pattern: АРТ.№ or similar product markers
        if re.match(r'арт\.?\s*№?\s*\d+', line_lower) or re.match(r'арт\.?\s*\d+', line_lower):
            # This is likely a product line
            # Get product name (everything after АРТ.№)
            product_name_match = re.search(r'арт\.?\s*№?\s*\d+\s+(.+)', line, re.IGNORECASE)
            if product_name_match:
                product_name = product_name_match.group(1).strip()
                
                # Look at next line(s) for quantity x price = total
                quantity = 1
                price = None
                item_total = None
                
                # Check next few lines for quantity/price pattern
                for j in range(i + 1, min(i + 5, len(lines))):
                    next_line = lines[j].strip()
                    if not next_line:
                        continue
                    
                    # Pattern: 1.000 x 36.50 = 36.50
                    qty_price_match = re.search(r'(\d+\.?\d*)\s*x\s*(\d+\.?\d*)\s*=\s*(\d+\.?\d*)', next_line)
                    if qty_price_match:
                        try:
                            quantity = float(qty_price_match.group(1))
                            price_uah = float(qty_price_match.group(2))
                            item_total_uah = float(qty_price_match.group(3))
                            price = int(price_uah * 100)  # Convert to kopecks
                            break
                        except ValueError:
                            pass
                    
                    # Pattern: just price at end: 36.50
                    price_only_match = re.search(r'(\d+\.?\d{2})\s*[А-ЯA-Z]?\s*$', next_line)
                    if price_only_match and not price:
                        try:
                            price_uah = float(price_only_match.group(1))
                            price = int(price_uah * 100)
                            break
                        except ValueError:
                            pass
                
                # If we found price, create item
                if price and price > 0:
                    line_items.append({
                        "name": product_name,
                        "quantity": quantity,
                        "price": price,
                        "confidence": 1.0,
                    })
                    # Skip the quantity/price line
                    if i + 1 < len(lines) and re.search(r'\d+\.?\d*\s*x\s*\d+', lines[i + 1]):
                        i += 1
        
        i += 1
    
    # Fallback: try generic parsing if no items found
    if not line_items:
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # Skip separator lines
            if line.startswith('-') or line.startswith('='):
                continue
            
            # Skip header/footer lines
            line_lower = line.lower()
            if any(skip in line_lower for skip in ['чек', 'check', 'фіскальний', 'fiscal', 'рро', 'rro', 'касовий', 'код уктзед', 'пдв', 'контрольне']):
                continue
            
            item = _parse_line_item(line)
            if item:
                line_items.append(item)
    
    result["line_items"] = line_items
    
    # Try to extract total if not found yet
    if not result["total"]:
        # Look for "СУМА ДО СПЛАТИ:" pattern first
        for line in lines:
            line_lower = line.lower()
            if 'сума до сплати' in line_lower or 'сума до оплати' in line_lower:
                total_match = re.search(r'(\d+[,.]?\d*)', line)
                if total_match:
                    total_str = total_match.group(1).replace(',', '.')
                    try:
                        total_uah = float(total_str)
                        result["total"] = int(total_uah * 100)
                        break
                    except ValueError:
                        pass
        
        # Look for total in other patterns
        if not result["total"]:
            for line in reversed(lines[-15:]):
                total_match = re.search(r'(?:сума|total|разом|всього)[\s:]*(\d+[,.]?\d*)', line, re.IGNORECASE)
                if total_match:
                    total_str = total_match.group(1).replace(',', '.')
                    try:
                        total_uah = float(total_str)
                        result["total"] = int(total_uah * 100)
                        break
                    except ValueError:
                        pass
    
    # Calculate total from items if not found
    if not result["total"] and line_items:
        calculated_total = sum(item.get("price", 0) * item.get("quantity", 1) for item in line_items)
        if calculated_total > 0:
            result["total"] = calculated_total
    
    return result


def _parse_line_item(line: str) -> dict[str, Any] | None:
    """
    Parse a single line item from receipt text.
    
    Args:
        line: Single line from receipt text
        
    Returns:
        Dictionary with item data or None if line doesn't contain item
    """
    # Skip lines that are clearly not items
    if any(skip in line.lower() for skip in ['чек', 'check', 'фіскальний', 'fiscal', 'рро', 'rro', 'дата', 'date', 'каса', 'cash']):
        return None
    
    # Pattern 1: "Назва товару" "кількість" "ціна" "сума"
    # Pattern 2: "Назва товару" "кількість x ціна = сума"
    # Pattern 3: "Назва товару" "ціна"
    
    # Try to find price in kopecks or UAH
    # Look for numbers followed by "грн" or "коп" or just numbers
    
    # Extract price (can be in UAH or kopecks)
    price_patterns = [
        r'(\d+[,.]?\d*)\s*грн',  # Price in UAH
        r'(\d+)\s*коп',  # Price in kopecks
        r'(\d+[,.]?\d{2})\s*$',  # Price at end of line
    ]
    
    price = None
    price_str = None
    
    for pattern in price_patterns:
        matches = list(re.finditer(pattern, line, re.IGNORECASE))
        if matches:
            # Take the last match (usually the total for the item)
            match = matches[-1]
            price_str = match.group(1).replace(',', '.')
            try:
                price_float = float(price_str)
                if 'коп' in line.lower() or 'коп' in match.group(0).lower():
                    price = int(price_float)
                else:
                    price = int(price_float * 100)  # Convert UAH to kopecks
                break
            except ValueError:
                continue
    
    # Extract quantity
    quantity = 1
    quantity_patterns = [
        r'(\d+)\s*x\s*\d+',  # "2 x 10.50"
        r'(\d+)\s*шт',  # "2 шт"
        r'(\d+)\s*шт\.',  # "2 шт."
        r'кількість[\s:]*(\d+)',  # "кількість: 2"
    ]
    
    for pattern in quantity_patterns:
        match = re.search(pattern, line, re.IGNORECASE)
        if match:
            try:
                quantity = int(match.group(1))
                break
            except ValueError:
                continue
    
    # Extract item name (everything before the price/quantity)
    # Remove price and quantity from line to get name
    name_line = line
    if price_str:
        # Remove price part
        name_line = re.sub(r'\d+[,.]?\d*\s*(?:грн|коп)', '', name_line, flags=re.IGNORECASE)
    # Remove quantity patterns
    name_line = re.sub(r'\d+\s*x\s*\d+', '', name_line)
    name_line = re.sub(r'\d+\s*шт\.?', '', name_line, flags=re.IGNORECASE)
    name_line = re.sub(r'кількість[\s:]*\d+', '', name_line, flags=re.IGNORECASE)
    
    # Clean up name
    name = name_line.strip()
    # Remove extra whitespace
    name = re.sub(r'\s+', ' ', name)
    # Remove common separators at start/end
    name = name.strip('.,;:')
    
    # Skip if name is too short or doesn't look like a product name
    if len(name) < 2 or len(name) > 200:
        return None
    
    # Skip if name is just numbers
    if re.match(r'^\d+$', name):
        return None
    
    # If we found a price, create item
    if price is not None and price > 0:
        return {
            "name": name,
            "quantity": quantity,
            "price": price,
            "confidence": 1.0,  # API data is reliable
        }
    
    # If no price found but name looks valid, try to extract from context
    # This is a fallback for cases where format is different
    if len(name) > 3:
        # Try to find any number that might be price
        numbers = re.findall(r'\d+[,.]?\d*', line)
        if numbers:
            try:
                # Take the last number as price
                price_str = numbers[-1].replace(',', '.')
                price_float = float(price_str)
                # Assume it's in UAH if it's a reasonable amount (< 10000)
                if price_float < 10000:
                    price = int(price_float * 100)
                    return {
                        "name": name,
                        "quantity": quantity,
                        "price": price,
                        "confidence": 0.8,  # Lower confidence for inferred price
                    }
            except ValueError:
                pass
    
    return None


def scrape_receipt_data_via_api(url: str, api_token: str | None = None) -> dict[str, Any]:
    """
    Scrape receipt data from tax.gov.ua using API (reserved as fallback method).
    
    Args:
        url: URL to the receipt page (cabinet.tax.gov.ua/cashregs/check?id=...)
        api_token: API token for tax.gov.ua (optional, will try to get from settings)
        
    Returns:
        Dictionary with receipt data in format compatible with ocr_payload
        
    Raises:
        ScrapingError: If scraping fails
    """
    import asyncio
    
    try:
        from apps.api_gateway.services.ocr.tax_api_client import (
            parse_receipt_url,
            fetch_receipt_data,
            TaxApiError
        )
    except ImportError as e:
        raise ScrapingError(f"Failed to import tax API client: {e}") from e
    
    # Get API token
    if not api_token:
        try:
            from libs.common import get_settings
            settings = get_settings()
            api_token = settings.tax_gov_ua_api_token
        except Exception as e:
            LOGGER.warning("Failed to get API token from settings: %s", e)
    
    if not api_token:
        raise ScrapingError("API token is required. Set TAX_GOV_UA_API_TOKEN environment variable or pass api_token parameter.")
    
    # Parse URL
    try:
        url_params = parse_receipt_url(url)
        receipt_id = url_params.get("id")
        if not receipt_id:
            raise ScrapingError("Could not extract receipt ID from URL")
    except Exception as e:
        raise ScrapingError(f"Failed to parse receipt URL: {e}") from e
    
    # Fetch data from API
    try:
        # Run async function in sync context
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is already running, create a new event loop in a thread
                import concurrent.futures
                import threading
                
                def run_in_thread():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(_fetch_receipt_data_async(
                            receipt_id=receipt_id,
                            token=api_token,
                            date=url_params.get("date"),
                            fn=url_params.get("fn"),
                        ))
                    finally:
                        new_loop.close()
                
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_in_thread)
                    api_response = future.result()
            else:
                api_response = loop.run_until_complete(_fetch_receipt_data_async(
                    receipt_id=receipt_id,
                    token=api_token,
                    date=url_params.get("date"),
                    fn=url_params.get("fn"),
                ))
        except RuntimeError:
            # No event loop, create a new one
            api_response = asyncio.run(_fetch_receipt_data_async(
                receipt_id=receipt_id,
                token=api_token,
                date=url_params.get("date"),
                fn=url_params.get("fn"),
            ))
    except TaxApiError as e:
        error_msg = str(e)
        # Check if it's a wartime restriction error
        if "воєнн" in error_msg.lower() or "обмежено доступ" in error_msg.lower() or "400" in error_msg:
            LOGGER.warning("API недоступен из-за ограничений военного положения")
            raise ScrapingError(f"Tax.gov.ua API недоступен: {error_msg}") from e
        raise ScrapingError(f"Tax.gov.ua API error: {e}") from e
    except Exception as e:
        raise ScrapingError(f"Failed to fetch receipt data: {e}") from e
    
    # Parse receipt text
    check_text = api_response.get("check", "")
    if not check_text:
        raise ScrapingError("Receipt text data not found in API response")
    
    parsed_data = parse_receipt_text(check_text)
    
    # Merge with API response data
    result = {
        "merchant": parsed_data.get("merchant") or api_response.get("name"),
        "purchase_ts": parsed_data.get("purchase_ts") or url_params.get("date"),
        "total": parsed_data.get("total"),
        "line_items": parsed_data.get("line_items", []),
        "confidence": {
            "mean": 1.0 if parsed_data.get("line_items") else 0.0,
            "min": 1.0 if parsed_data.get("line_items") else 0.0,
            "max": 1.0 if parsed_data.get("line_items") else 0.0,
            "token_count": len(check_text.split()),
            "auto_accept_candidate": len(parsed_data.get("line_items", [])) > 0,
        },
        "manual_review_required": len(parsed_data.get("line_items", [])) == 0,
        "anomalies": [],
    }
    
    # Add anomalies if needed
    if not result["line_items"]:
        result["anomalies"].append("No line items found in receipt text")
    if not result["total"]:
        result["anomalies"].append("Total amount not found")
    
    return result


def scrape_receipt_data(url: str, api_token: str | None = None) -> dict[str, Any]:
    """
    Scrape receipt data from tax.gov.ua using configured method with automatic fallback.
    
    Method selection:
    - "auto": Try Selenium first, fallback to API if Selenium fails
    - "selenium": Use Selenium only
    - "api": Use API only (reserved as fallback)
    
    Args:
        url: URL to the receipt page (cabinet.tax.gov.ua/cashregs/check?id=...)
        api_token: API token for tax.gov.ua (optional, will try to get from settings)
        
    Returns:
        Dictionary with receipt data in format compatible with ocr_payload
        
    Raises:
        ScrapingError: If scraping fails with all methods
    """
    from libs.common import get_settings
    settings = get_settings()
    method = settings.receipt_scraping_method
    
    LOGGER.info("Scraping receipt data using method: %s, url=%s", method, url)
    
    # Method: "api" - use API only
    if method == "api":
        try:
            return scrape_receipt_data_via_api(url, api_token)
        except ScrapingError as e:
            LOGGER.error("API scraping failed: %s", e)
            raise
    
    # Method: "selenium" - use Selenium only
    if method == "selenium":
        try:
            return scrape_receipt_data_via_selenium(url)
        except ScrapingError as e:
            LOGGER.error("Selenium scraping failed: %s", e)
            raise
    
    # Method: "auto" - try Selenium first, fallback to API
    if method == "auto":
        # Try Selenium first
        try:
            LOGGER.info("Trying Selenium method first...")
            return scrape_receipt_data_via_selenium(url)
        except ScrapingError as selenium_error:
            LOGGER.warning("Selenium scraping failed, falling back to API: %s", selenium_error)
            
            # Fallback to API
            try:
                LOGGER.info("Falling back to API method...")
                return scrape_receipt_data_via_api(url, api_token)
            except ScrapingError as api_error:
                LOGGER.error("Both Selenium and API methods failed")
                raise ScrapingError(
                    f"All scraping methods failed. Selenium: {selenium_error}, API: {api_error}"
                ) from api_error
    
    # Unknown method
    raise ScrapingError(f"Unknown scraping method: {method}. Use 'auto', 'selenium', or 'api'")


async def _fetch_receipt_data_async(
    receipt_id: str,
    token: str,
    date: str | None = None,
    fn: str | None = None,
) -> dict[str, Any]:
    """Helper function to fetch receipt data asynchronously."""
    from apps.api_gateway.services.ocr.tax_api_client import fetch_receipt_data
    return await fetch_receipt_data(
        receipt_id=receipt_id,
        token=token,
        date=date,
        fn=fn,
        receipt_type=3,  # Text document for display (UTF-8)
    )


def scrape_receipt_data_via_selenium(url: str) -> dict[str, Any]:
    """
    Scrape receipt data from tax.gov.ua using Selenium browser automation.
    
    Args:
        url: URL to the receipt page (cabinet.tax.gov.ua/cashregs/check?id=...)
        
    Returns:
        Dictionary with receipt data in format compatible with ocr_payload
        
    Raises:
        ScrapingError: If scraping fails
    """
    
    driver = None
    try:
        LOGGER.info("Starting Selenium browser for receipt scraping: url=%s", url)
        
        # Setup Chrome options
        options = webdriver.ChromeOptions()
        # Use headless mode for production
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # Additional options for Heroku/containerized environments
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-software-rasterizer')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-background-networking')
        options.add_argument('--disable-background-timer-throttling')
        options.add_argument('--disable-backgrounding-occluded-windows')
        options.add_argument('--disable-breakpad')
        options.add_argument('--disable-client-side-phishing-detection')
        options.add_argument('--disable-default-apps')
        options.add_argument('--disable-hang-monitor')
        options.add_argument('--disable-popup-blocking')
        options.add_argument('--disable-prompt-on-repost')
        options.add_argument('--disable-sync')
        options.add_argument('--disable-translate')
        options.add_argument('--metrics-recording-only')
        options.add_argument('--no-first-run')
        options.add_argument('--safebrowsing-disable-auto-update')
        options.add_argument('--enable-automation')
        options.add_argument('--password-store=basic')
        options.add_argument('--use-mock-keychain')
        
        # Set Chrome binary path for Heroku (if available)
        import os
        chrome_binary = os.environ.get('GOOGLE_CHROME_BIN') or '/usr/bin/google-chrome-stable'
        if os.path.exists(chrome_binary):
            options.binary_location = chrome_binary
        
        driver = webdriver.Chrome(options=options)
        driver.set_window_size(1920, 1080)
        
        LOGGER.debug("Loading page: %s", url)
        driver.get(url)
        
        # Wait for page to load
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(2)
        
        # Look for "Пошук" button and click it
        search_button = None
        selectors = [
            (By.XPATH, "//button[contains(text(), 'Пошук')]"),
            (By.XPATH, "//button[contains(text(), 'Поиск')]"),
            (By.XPATH, "//button[contains(text(), 'Search')]"),
            (By.XPATH, "//input[@type='submit' and contains(@value, 'Пошук')]"),
            (By.XPATH, "//input[@type='submit' and contains(@value, 'Поиск')]"),
            (By.XPATH, "//button[@type='submit']"),
            (By.CSS_SELECTOR, "button[type='submit']"),
        ]
        
        for by, selector in selectors:
            try:
                elements = driver.find_elements(by, selector)
                for elem in elements:
                    if elem.is_displayed():
                        text = elem.text or elem.get_attribute('value') or ''
                        if 'пошук' in text.lower() or 'поиск' in text.lower() or 'search' in text.lower() or not text:
                            search_button = elem
                            LOGGER.info("Found search button with selector: %s", selector)
                            break
                if search_button:
                    break
            except:
                continue
        
        if search_button:
            LOGGER.info("Clicking search button")
            driver.execute_script("arguments[0].click();", search_button)
            time.sleep(3)
            try:
                WebDriverWait(driver, 30).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
            except TimeoutException:
                LOGGER.warning("Timeout waiting for page load after button click")
        else:
            LOGGER.warning("Search button not found, using current page content")
        
        # Extract receipt content
        receipt_content = None
        
        # Strategy 1: Look for pre/code tags
        try:
            pre_elements = driver.find_elements(By.CSS_SELECTOR, "pre, code")
            for elem in pre_elements:
                if elem.is_displayed():
                    text = elem.text
                    if text and len(text) > 100 and any(kw in text.lower() for kw in ['чек', 'товар', 'сума', 'грн']):
                        receipt_content = text
                        LOGGER.debug("Found receipt content in pre/code tag")
                        break
        except:
            pass
        
        # Strategy 2: Look for main content
        if not receipt_content:
            try:
                main_selectors = ["main", "article", ".content", ".main", "#content"]
                for selector in main_selectors:
                    try:
                        elem = driver.find_element(By.CSS_SELECTOR, selector)
                        if elem.is_displayed():
                            receipt_content = elem.text
                            LOGGER.debug("Found receipt content in %s", selector)
                            break
                    except:
                        continue
            except:
                pass
        
        # Strategy 3: Use body text
        if not receipt_content:
            try:
                body = driver.find_element(By.TAG_NAME, "body")
                receipt_content = body.text
                LOGGER.debug("Using body text as receipt content")
            except:
                pass
        
        if not receipt_content:
            raise ScrapingError("Could not extract receipt content from page")
        
        LOGGER.info("Extracted receipt content: %d characters", len(receipt_content))
        
        # Parse the text
        parsed_data = parse_receipt_text(receipt_content)
        
        # Build result
        result = {
            "merchant": parsed_data.get("merchant"),
            "purchase_ts": parsed_data.get("purchase_ts"),
            "total": parsed_data.get("total"),
            "line_items": parsed_data.get("line_items", []),
            "confidence": {
                "mean": 0.9 if parsed_data.get("line_items") else 0.0,
                "min": 0.9 if parsed_data.get("line_items") else 0.0,
                "max": 0.9 if parsed_data.get("line_items") else 0.0,
                "token_count": len(receipt_content.split()),
                "auto_accept_candidate": len(parsed_data.get("line_items", [])) > 0,
            },
            "manual_review_required": len(parsed_data.get("line_items", [])) == 0,
            "anomalies": ["Данные получены через Selenium (браузерная автоматизация)"],
        }
        
        return result
        
    except Exception as e:
        error_msg = f"Selenium scraping failed: {e}"
        LOGGER.error(error_msg, exc_info=True)
        raise ScrapingError(error_msg) from e
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
