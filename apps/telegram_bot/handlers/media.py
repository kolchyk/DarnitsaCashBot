from __future__ import annotations

import asyncio
from uuid import uuid4

from aiogram import Bot, F, Router
from aiogram.types import Message

from libs.common.i18n import translate_status

from ..services import ReceiptApiClient

router = Router(name="media")

# Simple in-memory storage for pending receipts awaiting manual input
# In production, this should be replaced with Redis or database
_pending_receipts: dict[int, str] = {}  # telegram_id -> receipt_id


@router.message(F.photo)
async def handle_receipt_photo(message: Message, receipt_client: ReceiptApiClient):
    photo = message.photo[-1]
    if photo.file_size and photo.file_size > 10 * 1024 * 1024:
        await message.answer("Зображення чека перевищує 10 МБ. Надішліть менший файл.")
        return
    file = await message.bot.get_file(photo.file_id)
    file_bytes = await message.bot.download_file(file.file_path)
    content = file_bytes.read()

    await message.answer("Обробляємо ваш чек...")
    response = await receipt_client.upload_receipt(
        telegram_id=message.from_user.id,
        photo_bytes=content,
        filename=f"receipt-{uuid4()}.jpg",
        content_type="image/jpeg",
    )
    receipt_id = response["receipt"]["receipt_id"]
    status_translated = translate_status(response["receipt"]["status"])
    await message.answer(
        f"Чек отримано. Виплата PortmoneDirect почнеться після підтвердження. Поточний статус: {status_translated}"
    )
    
    # Check OCR status after a delay
    bot = message.bot
    asyncio.create_task(check_ocr_status(message.from_user.id, receipt_id, receipt_client, bot))


async def check_ocr_status(telegram_id: int, receipt_id: str, receipt_client: ReceiptApiClient, bot: Bot):
    """Check OCR status after processing and send appropriate message."""
    await asyncio.sleep(8)  # Wait for OCR to process
    
    try:
        status_response = await receipt_client.get_receipt_status(receipt_id=receipt_id)
        status = status_response.get("status")
        
        # If status is still pending, check again after more time
        if status == "pending":
            await asyncio.sleep(5)
            status_response = await receipt_client.get_receipt_status(receipt_id=receipt_id)
            status = status_response.get("status")
        
        # If OCR succeeded (processing or accepted), send success message
        if status in ("processing", "accepted"):
            darnitsa_products = status_response.get("darnitsa_products")
            
            if darnitsa_products and len(darnitsa_products) > 0:
                # Build detailed message about found Darnitsa products
                message_parts = ["✅ Чек успішно оброблено!\n\n"]
                message_parts.append("🎉 Знайдено препарат(и) Дарниця:\n\n")
                
                total_price = 0
                for product in darnitsa_products:
                    product_name = product.get("name", "Невідомий препарат")
                    price = product.get("price", 0)
                    quantity = product.get("quantity", 1)
                    total_price += price * quantity
                    
                    if quantity > 1:
                        message_parts.append(f"• {product_name}\n")
                        message_parts.append(f"  Кількість: {quantity} шт.\n")
                        message_parts.append(f"  Ціна: {price:.2f} грн за одиницю\n")
                        message_parts.append(f"  Сума: {price * quantity:.2f} грн\n\n")
                    else:
                        message_parts.append(f"• {product_name}\n")
                        message_parts.append(f"  Ціна: {price:.2f} грн\n\n")
                
                message_parts.append("💰 Бонус буде нараховано!\n\n")
                message_parts.append("💳 Вам буде зараховано 1 грн на мобільний телефон протягом години після підтвердження чека.\n")
                message_parts.append("Бонус надійде на номер телефону, який ви вказали в профілі.\n\n")
                message_parts.append("Дякуємо за вибір продукції Дарниця! 🙏")
                
                await bot.send_message(telegram_id, "".join(message_parts))
            else:
                # No Darnitsa products found - inform user
                await bot.send_message(
                    telegram_id,
                    "✅ Чек успішно розпізнано!\n\n"
                    "ℹ️ У вашому чеку не знайдено препаратів Дарниця.\n"
                    "Бонус нараховується тільки за покупку продукції Дарниця."
                )
        # If OCR failed (rejected), offer manual input
        elif status == "rejected":
            _pending_receipts[telegram_id] = receipt_id
            await bot.send_message(
                telegram_id,
                "❌ Не вдалося автоматично розпізнати чек. Будь ласка, введіть дані чека вручну.\n\n"
                "Формат введення:\n"
                "Назва товару, кількість, ціна\n"
                "Наприклад:\n"
                "Дарниця Цитрамон, 1, 50.00\n"
                "Дарниця Вітамін С, 2, 75.50\n\n"
                "Можете ввести кілька товарів, кожен з нового рядка."
            )
    except Exception as e:
        # If error checking status, don't bother user
        pass


@router.message(~F.photo & ~F.contact & ~F.text.startswith("/"))
async def fallback_handler(message: Message, receipt_client: ReceiptApiClient):
    telegram_id = message.from_user.id
    
    # Check if user is entering manual receipt data
    if telegram_id in _pending_receipts:
        receipt_id = _pending_receipts[telegram_id]
        text = message.text or ""
        
        # Parse manual input
        line_items = []
        for line in text.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            
            # Try to parse: "Product name, quantity, price"
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 3:
                name = parts[0]
                try:
                    quantity = int(parts[1])
                    price = parts[2]
                except (ValueError, IndexError):
                    await message.answer(
                        "❌ Помилка формату. Використовуйте формат: Назва товару, кількість, ціна\n"
                        "Наприклад: Дарниця Цитрамон, 1, 50.00"
                    )
                    return
            elif len(parts) == 2:
                # Assume quantity is 1
                name = parts[0]
                try:
                    quantity = 1
                    price = parts[1]
                except (ValueError, IndexError):
                    await message.answer(
                        "❌ Помилка формату. Використовуйте формат: Назва товару, кількість, ціна"
                    )
                    return
            else:
                await message.answer(
                    "❌ Помилка формату. Використовуйте формат: Назва товару, кількість, ціна"
                )
                return
            
            line_items.append({
                "name": name,
                "quantity": quantity,
                "price": price,
            })
        
        if not line_items:
            await message.answer("❌ Не вдалося розпізнати дані. Спробуйте ще раз.")
            return
        
        # Submit manual data
        try:
            await receipt_client.submit_manual_receipt_data(
                receipt_id=receipt_id,
                merchant=None,
                purchase_date=None,
                line_items=line_items,
            )
            del _pending_receipts[telegram_id]
            await message.answer(
                "✅ Дані чека отримано. Вони будуть перевірені та нараховано кешбек."
            )
        except Exception as e:
            await message.answer(
                "❌ Помилка при збереженні даних. Спробуйте ще раз або зверніться до підтримки."
            )
        return
    
    await message.answer("Надішліть фото чека або скористайтеся /help для інструкцій.")

