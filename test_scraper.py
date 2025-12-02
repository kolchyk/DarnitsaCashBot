import sys
import os
sys.path.insert(0, '.')
os.environ.setdefault('TELEGRAM_BOT_TOKEN', 'dummy')
os.environ.setdefault('ENCRYPTION_SECRET', 'dummy_secret')

from services.ocr_worker.receipt_scraper import scrape_receipt_data

url = 'https://cabinet.tax.gov.ua/cashregs/check?id=UxI07gWmYOQ&date=20251201&time=16:12&fn=4001246197&sm=46.50'

print('='*80)
print('ПОЛУЧЕНИЕ ДАННЫХ ЧЕКА')
print('='*80)
print(f'URL: {url}\n')

try:
    print('Запрос к серверу...')
    data = scrape_receipt_data(url)
    
    print('\n✅ Данные получены!\n')
    print('ОСНОВНАЯ ИНФОРМАЦИЯ:')
    print(f'  Торговец: {data.get("merchant", "не определен")}')
    print(f'  Дата: {data.get("purchase_ts", "не определена")}')
    
    total = data.get('total')
    if total:
        print(f'  Сумма: {total / 100:.2f} грн ({total} копеек)')
    
    items = data.get('line_items', [])
    print(f'\nПОЗИЦИИ ЧЕКА ({len(items)}):')
    print('-'*80)
    
    for i, item in enumerate(items, 1):
        name = item.get('name', 'неизвестно')
        qty = item.get('quantity', 1)
        price = item.get('price', 0)
        price_uah = price / 100
        
        print(f'\n{i}. {name}')
        print(f'   Количество: {qty} шт.')
        print(f'   Цена: {price_uah:.2f} грн ({price} копеек)')
        if qty > 1:
            total_item = price * qty
            print(f'   Итого: {total_item / 100:.2f} грн')
    
    print('\n' + '='*80)
    
except Exception as e:
    print(f'\n❌ Ошибка: {e}')
    import traceback
    traceback.print_exc()

