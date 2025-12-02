import sys
import os
sys.path.insert(0, '.')
os.environ.setdefault('TELEGRAM_BOT_TOKEN', 'dummy')
os.environ.setdefault('ENCRYPTION_SECRET', 'dummy_secret')

import httpx

url = 'https://cabinet.tax.gov.ua/cashregs/check?id=UxI07gWmYOQ&date=20251201&time=16:12&fn=4001246197&sm=46.50'

print('Запрос к серверу...')
with httpx.Client(timeout=30.0, follow_redirects=True) as client:
    response = client.get(url)
    response.raise_for_status()
    html_content = response.text

# Сохраняем HTML для анализа
with open('receipt_page.html', 'w', encoding='utf-8') as f:
    f.write(html_content)

print(f'HTML сохранен в receipt_page.html ({len(html_content)} символов)')
print(f'Первые 2000 символов:')
print(html_content[:2000])

