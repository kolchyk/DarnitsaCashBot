import sys
import os
import httpx
import json
import re

url = 'https://cabinet.tax.gov.ua/cashregs/check?id=UxI07gWmYOQ&date=20251201&time=16:12&fn=4001246197&sm=46.50'

# Извлекаем параметры из URL
match = re.search(r'id=([^&]+)', url)
check_id = match.group(1) if match else None

print(f"ID чека: {check_id}")

# Попробуем различные варианты API endpoints
api_endpoints = [
    f'https://cabinet.tax.gov.ua/api/cashregs/check/{check_id}',
    f'https://cabinet.tax.gov.ua/api/checks/{check_id}',
    f'https://cabinet.tax.gov.ua/api/receipt/{check_id}',
    f'https://cabinet.tax.gov.ua/cashregs/api/check?id={check_id}',
]

with httpx.Client(timeout=30.0, follow_redirects=True) as client:
    for api_url in api_endpoints:
        try:
            print(f"\nПробуем: {api_url}")
            response = client.get(api_url, headers={
                'Accept': 'application/json',
                'User-Agent': 'Mozilla/5.0'
            })
            print(f"Статус: {response.status_code}")
            if response.status_code == 200:
                try:
                    data = response.json()
                    print("✅ JSON данные получены!")
                    print(json.dumps(data, indent=2, ensure_ascii=False)[:1000])
                    break
                except:
                    print(f"Ответ не JSON: {response.text[:200]}")
        except Exception as e:
            print(f"Ошибка: {e}")

