from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

LOGGER = logging.getLogger(__name__)


class TaxApiError(Exception):
    """Raised when tax.gov.ua API request fails."""


def parse_receipt_url(url: str) -> dict[str, str | None]:
    """
    Parse receipt URL to extract parameters needed for API request.
    
    Args:
        url: URL from QR code (e.g., https://cabinet.tax.gov.ua/cashregs/check?id=...&date=...&time=...&fn=...)
        
    Returns:
        Dictionary with parsed parameters: id, date, fn
    """
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        
        # Extract id (required)
        id_value = params.get("id", [None])[0]
        
        # Extract and combine date and time
        date_value = params.get("date", [None])[0]  # Format: YYYYMMDD
        time_value = params.get("time", [None])[0]  # Format: HH:mm
        
        # Combine date and time into YYYY-MM-DD HH:mm:ss format
        formatted_date = None
        if date_value and time_value:
            try:
                # Parse date from YYYYMMDD format
                date_obj = datetime.strptime(date_value, "%Y%m%d")
                # Combine with time
                time_parts = time_value.split(":")
                if len(time_parts) >= 2:
                    hour = int(time_parts[0])
                    minute = int(time_parts[1])
                    second = int(time_parts[2]) if len(time_parts) > 2 else 0
                    date_obj = date_obj.replace(hour=hour, minute=minute, second=second)
                    formatted_date = date_obj.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, IndexError) as e:
                LOGGER.warning("Failed to parse date/time from URL: date=%s, time=%s, error=%s", date_value, time_value, e)
        elif date_value:
            # If only date is available, use 00:00:00 as default time
            try:
                date_obj = datetime.strptime(date_value, "%Y%m%d")
                formatted_date = date_obj.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError as e:
                LOGGER.warning("Failed to parse date from URL: date=%s, error=%s", date_value, e)
        
        # Extract fn (fiscal number)
        fn_value = params.get("fn", [None])[0]
        
        return {
            "id": id_value,
            "date": formatted_date,
            "fn": fn_value,
        }
    except Exception as e:
        LOGGER.error("Failed to parse receipt URL: url=%s, error=%s", url, e, exc_info=True)
        raise TaxApiError(f"Failed to parse receipt URL: {e}") from e


async def fetch_receipt_data(
    receipt_id: str,
    token: str,
    date: str | None = None,
    fn: str | None = None,
    receipt_type: int = 3,
) -> dict[str, Any]:
    """
    Fetch receipt data from tax.gov.ua API.
    
    Args:
        receipt_id: Check ID (required)
        token: Authorization token (required)
        date: Date in format YYYY-MM-DD HH:mm:ss (optional)
        fn: Fiscal number RRO (optional)
        receipt_type: Type of receipt (1 - Original XML, 2 - XML signed with KEP, 3 - Text document for display UTF-8)
        
    Returns:
        Dictionary with receipt data from API
        
    Raises:
        TaxApiError: If API request fails
    """
    api_url = "https://cabinet.tax.gov.ua/ws/api_public/rro/chkAll"
    
    # Build request payload
    payload: dict[str, Any] = {
        "id": receipt_id,
        "type": receipt_type,
        "token": token,
    }
    
    if date:
        payload["date"] = date
    if fn:
        payload["fn"] = fn
    
    # Create payload copy for logging (without sensitive token)
    payload_for_logging = {**payload}
    if "token" in payload_for_logging:
        payload_for_logging["token"] = f"{token[:8]}..." if len(token) > 8 else "***"
    
    LOGGER.info(
        "Requesting receipt data from tax.gov.ua API:\n"
        "  Request URL: %s\n"
        "  Method: POST\n"
        "  Payload: id=%s, date=%s, fn=%s, type=%d, token=%s",
        api_url,
        receipt_id,
        date,
        fn,
        receipt_type,
        payload_for_logging.get("token", "***"),
    )
    
    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(api_url, json=payload)
            elapsed_time = time.time() - start_time
            
            # Log response details before raising for status
            LOGGER.info(
                "Tax.gov.ua API response received:\n"
                "  Request URL: %s\n"
                "  Status Code: %d\n"
                "  Response Time: %.3f seconds\n"
                "  Response Size: %d bytes",
                api_url,
                response.status_code,
                elapsed_time,
                len(response.content),
            )
            
            response.raise_for_status()
            
            data = response.json()
            LOGGER.info(
                "Successfully received receipt data from tax.gov.ua API:\n"
                "  Request URL: %s\n"
                "  Receipt ID: %s\n"
                "  Fiscal Number (fn): %s\n"
                "  XML Available: %s\n"
                "  Signed: %s\n"
                "  Check Data Length: %d characters\n"
                "  Response Time: %.3f seconds",
                api_url,
                receipt_id,
                data.get("fn"),
                data.get("xml"),
                data.get("sign"),
                len(data.get("check", "")),
                elapsed_time,
            )
            
            return data
    except httpx.HTTPStatusError as e:
        elapsed_time = time.time() - start_time
        error_msg = f"Tax.gov.ua API returned error status {e.response.status_code}"
        if e.response.text:
            error_msg += f": {e.response.text}"
        LOGGER.error(
            "Tax.gov.ua API error:\n"
            "  Request URL: %s\n"
            "  Status Code: %d\n"
            "  Response Time: %.3f seconds\n"
            "  Error: %s\n"
            "  Response Body: %s",
            api_url,
            e.response.status_code,
            elapsed_time,
            error_msg,
            e.response.text[:500] if e.response.text else "No response body",
        )
        raise TaxApiError(error_msg) from e
    except httpx.RequestError as e:
        elapsed_time = time.time() - start_time
        error_msg = f"Request error while calling tax.gov.ua API: {e}"
        LOGGER.error(
            "Tax.gov.ua API request error:\n"
            "  Request URL: %s\n"
            "  Response Time: %.3f seconds\n"
            "  Error: %s",
            api_url,
            elapsed_time,
            error_msg,
        )
        raise TaxApiError(error_msg) from e
    except Exception as e:
        elapsed_time = time.time() - start_time
        error_msg = f"Unexpected error while calling tax.gov.ua API: {e}"
        LOGGER.error(
            "Tax.gov.ua API unexpected error:\n"
            "  Request URL: %s\n"
            "  Response Time: %.3f seconds\n"
            "  Error: %s",
            api_url,
            elapsed_time,
            error_msg,
            exc_info=True,
        )
        raise TaxApiError(error_msg) from e

