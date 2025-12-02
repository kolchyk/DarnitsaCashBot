import sys
import os
sys.path.insert(0, '.')
os.environ.setdefault('TELEGRAM_BOT_TOKEN', 'dummy')
os.environ.setdefault('ENCRYPTION_SECRET', 'dummy_secret')

from services.ocr_worker.qr_scanner import detect_qr_code

with open('5292124673841762126.jpg', 'rb') as f:
    data = f.read()

result = detect_qr_code(data)

print('='*80)
print('РЕЗУЛЬТАТ РАСПОЗНАВАНИЯ QR-КОДА')
print('='*80)
if result:
    print(f'\n✅ QR-код успешно распознан!')
    print(f'\nURL: {result}')
    print(f'\nДетали:')
    print(f'  - Длина: {len(result)} символов')
    print(f'  - Тип: {"URL" if result.startswith(("http://", "https://")) else "Текст"}')
    if result.startswith('https://'):
        print(f'  - Протокол: HTTPS')
    elif result.startswith('http://'):
        print(f'  - Протокол: HTTP')
else:
    print('\n❌ QR-код не найден')
print('='*80)

