#!/usr/bin/env python3
"""Скрипт для тестирования пополнения счета через Portmone API."""

import argparse
import asyncio
import os
import ssl
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

if not os.getenv("ENCRYPTION_SECRET"):
    os.environ["ENCRYPTION_SECRET"] = "test-secret-key-for-topup-testing-only"
if not os.getenv("TELEGRAM_BOT_TOKEN"):
    os.environ["TELEGRAM_BOT_TOKEN"] = "test-token"

import httpx
from libs.common.config import get_settings
from libs.common.portmone import (
    PortmoneResponseError,
    PortmoneTransportError,
    get_operator_payee_id,
    parse_portmone_response,
)


async def test_topup(phone_number: str, amount: float, use_mock: bool = False):
    """Тестирует пополнение счета через Portmone API."""
    settings = get_settings()
    
    if use_mock:
        settings.portmone_api_base = "http://localhost:8082/api/directcash/"
    
    payee_id = get_operator_payee_id(phone_number, settings)
    amount_str = f"{amount:.2f}"
    
    payload = {
        "method": "bills.create",
        "login": settings.portmone_login,
        "password": settings.portmone_password,
        "version": settings.portmone_version,
        "payeeId": payee_id,
        "contractNumber": phone_number,
        "amount": amount_str,
        "currency": settings.portmone_default_currency,
        "comment": f"Test top-up for {phone_number}"
    }
    if settings.portmone_lang:
        payload["lang"] = settings.portmone_lang
    
    cert = None
    if settings.portmone_cert_path:
        cert_path = Path(settings.portmone_cert_path)
        if cert_path.exists() and cert_path.is_file():
            # Check if we have a separate key file
            if settings.portmone_key_path:
                key_path = Path(settings.portmone_key_path)
                if key_path.exists() and key_path.is_file():
                    # Use tuple format for separate cert and key files
                    cert = (str(cert_path), str(key_path))
                else:
                    print(f"Ошибка: файл ключа не найден: {settings.portmone_key_path}")
                    return False
            else:
                # Single file should contain both certificate and private key in PEM format
                cert = str(cert_path)
        else:
            print(f"Ошибка: файл сертификата не найден: {settings.portmone_cert_path}")
            return False
    
    try:
        # Configure SSL context for TLS 1.2 (Portmone only supports TLS 1.2)
        # Only apply SSL context for HTTPS URLs (not for HTTP mock servers)
        ssl_context = None
        if settings.portmone_api_base.startswith("https://"):
            ssl_context = ssl.create_default_context()
            # Enforce TLS 1.2 (Portmone requirement)
            ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
            ssl_context.maximum_version = ssl.TLSVersion.TLSv1_2
            # Verify server certificate
            ssl_context.check_hostname = True
            ssl_context.verify_mode = ssl.CERT_REQUIRED
        
        # For Portmone API with client certificate, we need to verify server cert and send client cert
        async with httpx.AsyncClient(
            timeout=30.0, 
            cert=cert,
            verify=ssl_context if ssl_context else True  # Use custom SSL context with TLS 1.2 for HTTPS, default for HTTP
        ) as http_client:
            response = await http_client.post(
                settings.portmone_api_base.rstrip("/") + "/",
                data=payload
            )
            
            if response.status_code != 200:
                print(f"HTTP ошибка {response.status_code}: {response.text}")
                return False
            
            parsed = parse_portmone_response(response.text)
            
            if parsed.status != "ok":
                print(f"API ошибка: {parsed.status}")
                if parsed.errors:
                    for error in parsed.errors:
                        print(f"  {error.code}: {error.message}")
                return False
            
            print(f"Успех! Bill ID: {parsed.bill_id}")
            return True
        
    except PortmoneResponseError as e:
        print(f"API ошибка: {e.response.status}")
        if e.response.errors:
            for error in e.response.errors:
                print(f"  {error.code}: {error.message}")
        return False
        
    except PortmoneTransportError as e:
        print(f"Ошибка подключения: {e}")
        return False
        
    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description="Тестирование пополнения счета через Portmone API")
    parser.add_argument("--phone", type=str, default="380992227160", help="Номер телефона")
    parser.add_argument("--amount", type=float, default=1.00, help="Сумма пополнения")
    parser.add_argument("--mock", action="store_true", help="Использовать mock-сервер")
    
    args = parser.parse_args()
    
    phone = args.phone.strip()
    if not phone.startswith("380") or len(phone) != 12:
        print(f"Неверный формат номера: {phone}")
        sys.exit(1)
    
    if args.amount <= 0:
        print(f"Сумма должна быть положительной: {args.amount}")
        sys.exit(1)
    
    success = asyncio.run(test_topup(phone, args.amount, use_mock=args.mock))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

