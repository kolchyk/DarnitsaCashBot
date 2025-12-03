#!/usr/bin/env python
"""
Тестовый скрипт для парсинга страницы чека с tax.gov.ua
Использование: python scripts/test_parse_page.py [url]
"""
from __future__ import annotations

import sys
import json
import logging
from pathlib import Path
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Добавляем корень проекта в путь
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


def test_parse_page(url: str, save_html: bool = True, api_token: str | None = None) -> None:
    """
    Тестирует парсинг страницы чека с tax.gov.ua через браузерную автоматизацию
    
    Args:
        url: URL страницы чека
        save_html: Сохранять ли HTML для отладки
        api_token: API токен для tax.gov.ua (не используется, оставлен для совместимости)
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException
    except ImportError:
        print("\n❌ Библиотека Selenium не установлена!")
        print("   Установите: pip install selenium")
        return None
    
    from apps.api_gateway.services.ocr.receipt_scraper import parse_receipt_text
    
    print("=" * 80)
    print("ТЕСТ ПАРСИНГА СТРАНИЦЫ ЧЕКА")
    print("=" * 80)
    print(f"\n🔗 URL: {url}")
    print(f"⏰ Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 80)
    
    driver = None
    try:
        print("\n🚀 Запускаем браузер...")
        # Используем Chrome
        options = webdriver.ChromeOptions()
        # Раскомментируйте следующую строку для headless режима
        # options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        driver = webdriver.Chrome(options=options)
        driver.set_window_size(1920, 1080)
        
        print(f"📄 Загружаем страницу: {url}")
        driver.get(url)
        
        print("⏳ Ожидаем загрузки страницы...")
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Дополнительная задержка для полной загрузки
        import time
        time.sleep(2)
        
        # Ищем кнопку "Пошук"
        print("🔍 Ищем кнопку 'Пошук'...")
        search_button = None
        
        # Пробуем разные способы найти кнопку
        selectors = [
            (By.XPATH, "//button[contains(text(), 'Пошук')]"),
            (By.XPATH, "//button[contains(text(), 'Поиск')]"),
            (By.XPATH, "//button[contains(text(), 'Search')]"),
            (By.XPATH, "//input[@type='submit' and contains(@value, 'Пошук')]"),
            (By.XPATH, "//input[@type='submit' and contains(@value, 'Поиск')]"),
            (By.XPATH, "//button[@type='submit']"),
            (By.CSS_SELECTOR, "button[type='submit']"),
            (By.CSS_SELECTOR, "input[type='submit']"),
        ]
        
        for by, selector in selectors:
            try:
                elements = driver.find_elements(by, selector)
                for elem in elements:
                    if elem.is_displayed():
                        text = elem.text or elem.get_attribute('value') or ''
                        if 'пошук' in text.lower() or 'поиск' in text.lower() or 'search' in text.lower() or not text:
                            search_button = elem
                            print(f"✅ Найдена кнопка: {text or selector}")
                            break
                if search_button:
                    break
            except:
                continue
        
        # Если не нашли по селекторам, ищем все кнопки
        if not search_button:
            try:
                all_buttons = driver.find_elements(By.TAG_NAME, "button")
                for btn in all_buttons:
                    if btn.is_displayed():
                        text = btn.text.lower()
                        if 'пошук' in text or 'поиск' in text or 'search' in text:
                            search_button = btn
                            print(f"✅ Найдена кнопка с текстом: {btn.text}")
                            break
            except:
                pass
        
        if search_button:
            print("🖱️  Кликаем на кнопку 'Пошук'...")
            driver.execute_script("arguments[0].click();", search_button)
            
            print("⏳ Ожидаем загрузки результатов...")
            time.sleep(3)  # Ждем загрузки результатов
            
            # Ждем изменения контента
            try:
                WebDriverWait(driver, 30).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
            except TimeoutException:
                print("⚠️  Таймаут ожидания загрузки, продолжаем...")
        else:
            print("⚠️  Кнопка 'Пошук' не найдена, используем текущий контент страницы")
        
        # Получаем HTML контент
        print("📥 Получаем контент страницы...")
        html_content = driver.page_source
        
        # Получаем текстовый контент
        receipt_content = None
        
        # Стратегия 1: Ищем pre/code теги
        try:
            pre_elements = driver.find_elements(By.CSS_SELECTOR, "pre, code")
            for elem in pre_elements:
                if elem.is_displayed():
                    text = elem.text
                    if text and len(text) > 100 and any(kw in text.lower() for kw in ['чек', 'товар', 'сума', 'грн']):
                        receipt_content = text
                        print("✅ Найден контент чека в pre/code теге")
                        break
        except:
            pass
        
        # Стратегия 2: Ищем в основном контенте
        if not receipt_content:
            try:
                main_selectors = ["main", "article", ".content", ".main", "#content"]
                for selector in main_selectors:
                    try:
                        elem = driver.find_element(By.CSS_SELECTOR, selector)
                        if elem.is_displayed():
                            receipt_content = elem.text
                            print(f"✅ Найден контент в {selector}")
                            break
                    except:
                        continue
            except:
                pass
        
        # Стратегия 3: Берем весь body
        if not receipt_content:
            try:
                body = driver.find_element(By.TAG_NAME, "body")
                receipt_content = body.text
                print("✅ Используем весь контент body")
            except:
                pass
        
        # Сохраняем HTML если нужно
        html_file = None
        if save_html:
            output_dir = PROJECT_ROOT / "scripts" / "test_results"
            output_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            html_file = output_dir / f"receipt_page_{timestamp}.html"
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(html_content)
            print(f"💾 HTML сохранен в: {html_file}")
        
        # Парсим полученный текст
        print("\n📋 Парсим полученный контент...")
        if not receipt_content:
            raise Exception("Не удалось получить контент со страницы")
        
        result = parse_receipt_text(receipt_content)
        
        # Добавляем информацию о методе получения данных
        result["source"] = "web_scraping"
        result["html_saved"] = str(html_file) if html_file else None
        
        print("\n" + "=" * 80)
        print("✅ ПАРСИНГ УСПЕШЕН!")
        print("=" * 80)
        
        # Основная информация
        print("\n📋 ОСНОВНАЯ ИНФОРМАЦИЯ:")
        print(f"   Торговец: {result.get('merchant') or 'Не найдено'}")
        print(f"   Дата покупки: {result.get('purchase_ts') or 'Не найдено'}")
        
        total = result.get('total')
        if total:
            total_uah = total / 100
            print(f"   Сумма: {total_uah:.2f} грн ({total} копеек)")
        else:
            print(f"   Сумма: Не найдено")
        
        line_items = result.get('line_items', [])
        print(f"   Количество позиций: {len(line_items)}")
        
        # Детали позиций
        if line_items:
            print("\n📦 ПОЗИЦИИ В ЧЕКЕ:")
            print("-" * 80)
            total_calculated = 0
            for i, item in enumerate(line_items, 1):
                name = item.get('name', 'Без названия')
                quantity = item.get('quantity', 1)
                price = item.get('price', 0)
                price_uah = price / 100
                item_total = price * quantity
                item_total_uah = item_total / 100
                total_calculated += item_total
                
                print(f"\n   {i}. {name}")
                print(f"      Количество: {quantity}")
                print(f"      Цена за единицу: {price_uah:.2f} грн ({price} копеек)")
                print(f"      Сумма позиции: {item_total_uah:.2f} грн ({item_total} копеек)")
                print(f"      Уверенность: {item.get('confidence', 1.0):.2%}")
                
                if item.get('is_darnitsa'):
                    print(f"      ✅ Продукт Darnitsa")
                if item.get('sku_code'):
                    print(f"      SKU: {item.get('sku_code')}")
            
            print("\n" + "-" * 80)
            print(f"   Итого по позициям: {total_calculated / 100:.2f} грн ({total_calculated} копеек)")
        else:
            print("\n⚠️  Позиции не найдены!")
        
        # Статистика уверенности
        confidence = result.get('confidence', {})
        if confidence:
            print("\n📊 СТАТИСТИКА УВЕРЕННОСТИ:")
            print(f"   Средняя уверенность: {confidence.get('mean', 0):.2%}")
            print(f"   Минимальная: {confidence.get('min', 0):.2%}")
            print(f"   Максимальная: {confidence.get('max', 0):.2%}")
            print(f"   Количество токенов: {confidence.get('token_count', 0)}")
            print(f"   Автопринятие: {'Да' if confidence.get('auto_accept_candidate') else 'Нет'}")
        
        # Дополнительная информация
        print("\n🔍 ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ:")
        print(f"   Требуется ручная проверка: {'Да' if result.get('manual_review_required') else 'Нет'}")
        
        anomalies = result.get('anomalies', [])
        if anomalies:
            print(f"   ⚠️  Аномалии найдены: {len(anomalies)}")
            for anomaly in anomalies:
                print(f"      - {anomaly}")
        else:
            print(f"   Аномалии: Не найдено")
        
        # Сохранение результатов
        output_dir = PROJECT_ROOT / "scripts" / "test_results"
        output_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_file = output_dir / f"parse_result_{timestamp}.json"
        
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"\n💾 Полный результат сохранен в: {json_file}")
        
        return result
        
    except TimeoutException as e:
        print("\n" + "=" * 80)
        print("❌ ОШИБКА ТАЙМАУТА")
        print("=" * 80)
        print(f"\nПревышено время ожидания: {str(e)}")
        return None
    except Exception as e:
        print("\n" + "=" * 80)
        print("❌ ОШИБКА ПАРСИНГА")
        print("=" * 80)
        print(f"\nТип ошибки: {type(e).__name__}")
        print(f"Сообщение: {str(e)}")
        print("\nПолный traceback:")
        import traceback
        traceback.print_exc()
        return None
    finally:
        if driver:
            print("\n🔒 Закрываем браузер...")
            driver.quit()


def main() -> None:
    """Главная функция."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Тест парсинга страницы чека с tax.gov.ua"
    )
    parser.add_argument(
        "url",
        nargs="?",
        default="https://cabinet.tax.gov.ua/cashregs/check?id=UxI07gWmYOQ&date=20251201&time=16:12&fn=4001246197&sm=46.50",
        help="URL страницы чека"
    )
    parser.add_argument(
        "--token",
        help="API токен для tax.gov.ua (опционально, можно использовать TAX_GOV_UA_API_TOKEN)"
    )
    parser.add_argument(
        "--save-html",
        action="store_true",
        help="Сохранять HTML для отладки (не используется)"
    )
    
    args = parser.parse_args()
    
    result = test_parse_page(args.url, save_html=args.save_html, api_token=args.token)
    
    print("\n" + "=" * 80)
    if result:
        print("✅ Тест завершен успешно")
    else:
        print("❌ Тест завершен с ошибками")
    print("=" * 80)


if __name__ == "__main__":
    main()

