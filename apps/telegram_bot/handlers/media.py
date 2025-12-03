from __future__ import annotations

import asyncio
from uuid import uuid4

import httpx
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
    # Check if user has phone number before processing receipt
    try:
        user_info = await receipt_client.register_user(
            telegram_id=message.from_user.id,
            phone_number=None,
            locale="uk",
        )
        if not user_info.get("has_phone"):
            from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
            contact_keyboard = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="Поділитися номером телефону", request_contact=True)]],
                resize_keyboard=True,
                one_time_keyboard=True,
            )
            await message.answer(
                "📱 <b>Потрібен номер телефону</b>\n\n"
                "Для виплати бонусу нам потрібен ваш номер телефону.\n\n"
                "💡 Ми надсилаємо поповнення 1₴ безпосередньо на ваш мобільний телефон після підтвердження чека.\n\n"
                "👇 Будь ласка, поділіться номером телефону, натиснувши кнопку нижче.",
                reply_markup=contact_keyboard,
                parse_mode="HTML",
            )
            return
    except Exception as e:
        # If we can't check user info, proceed with upload and let API handle it
        pass

    photo = message.photo[-1]
    if photo.file_size and photo.file_size > 10 * 1024 * 1024:
        await message.answer(
            "❌ <b>Файл занадто великий</b>\n\n"
            "Зображення чека перевищує 10 МБ.\n\n"
            "💡 Спробуйте надіслати менший файл або зменште якість фото.",
            parse_mode="HTML",
        )
        return
    file = await message.bot.get_file(photo.file_id)
    file_bytes = await message.bot.download_file(file.file_path)
    content = file_bytes.read()

    await message.answer(
        "🔄 <b>Обробка чека</b>\n\n"
        "Ваш чек отримано та обробляється...\n\n"
        "⏳ Це може зайняти 1-2 хвилини.\n"
        "Ви отримаєте повідомлення про результат.",
        parse_mode="HTML",
    )
    try:
        response = await receipt_client.upload_receipt(
            telegram_id=message.from_user.id,
            photo_bytes=content,
            filename=f"receipt-{uuid4()}.jpg",
            content_type="image/jpeg",
        )
        receipt_id = response["receipt"]["receipt_id"]
        status_translated = translate_status(response["receipt"]["status"])
        await message.answer(
            f"✅ <b>Чек отримано!</b>\n\n"
            f"📋 Статус: {status_translated}\n\n"
            f"⏳ Зачекайте, будь ласка. Ми обробляємо ваш чек та перевіряємо наявність продуктів Дарниця.\n\n"
            f"💡 Ви отримаєте повідомлення про результат обробки.",
            parse_mode="HTML",
        )
        
        # Check receipt processing status after a delay
        bot = message.bot
        asyncio.create_task(check_receipt_status(message.from_user.id, receipt_id, receipt_client, bot))
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400 and "phone" in e.response.text.lower():
            from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
            contact_keyboard = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="Поділитися номером телефону", request_contact=True)]],
                resize_keyboard=True,
                one_time_keyboard=True,
            )
            await message.answer(
                "⚠️ Для виплати бонусу нам потрібен ваш номер телефону.\n\n"
                "Будь ласка, поділіться номером телефону, натиснувши кнопку нижче.",
                reply_markup=contact_keyboard,
            )
        else:
            error_msg = e.response.text if hasattr(e.response, 'text') else "Невідома помилка"
            await message.answer(
                f"❌ <b>Помилка при завантаженні чека</b>\n\n"
                f"Деталі: {error_msg}\n\n"
                f"💡 <b>Що робити:</b>\n"
                f"• Перевірте якість фото\n"
                f"• Переконайтеся, що на чеку є QR код\n"
                f"• Спробуйте надіслати фото ще раз\n\n"
                f"Якщо проблема повторюється, зверніться до підтримки.",
                parse_mode="HTML",
            )
    except TimeoutError as e:
        await message.answer(
            "⏱️ <b>Час очікування вичерпано</b>\n\n"
            "Час очікування при завантаженні чека вичерпано.\n\n"
            "💡 <b>Що робити:</b>\n"
            "• Перевірте з'єднання з інтернетом\n"
            "• Переконайтеся, що ваше інтернет-з'єднання стабільне\n"
            "• Спробуйте надіслати фото ще раз\n\n"
            "Якщо проблема повторюється, зверніться до підтримки.",
            parse_mode="HTML",
        )
    except ConnectionError as e:
        await message.answer(
            "❌ <b>Помилка з'єднання</b>\n\n"
            "Не вдалося підключитися до сервера.\n\n"
            "💡 <b>Можливі причини:</b>\n"
            "• Проблеми з інтернет-з'єднанням\n"
            "• Тимчасові проблеми на сервері\n\n"
            "🔄 Будь ласка, спробуйте пізніше або зверніться до підтримки.",
            parse_mode="HTML",
        )
    except Exception as e:
        await message.answer(
            "❌ <b>Сталася помилка</b>\n\n"
            "Під час завантаження чека сталася несподівана помилка.\n\n"
            "💡 <b>Що робити:</b>\n"
            "• Перевірте якість фото\n"
            "• Переконайтеся, що на чеку є QR код\n"
            "• Спробуйте надіслати фото ще раз\n\n"
            "Якщо проблема повторюється, зверніться до підтримки.",
            parse_mode="HTML",
        )


async def check_receipt_status(telegram_id: int, receipt_id: str, receipt_client: ReceiptApiClient, bot: Bot):
    """Check receipt processing status after QR code scanning and send appropriate message."""
    await asyncio.sleep(8)  # Wait for QR code processing
    
    try:
        status_response = await receipt_client.get_receipt_status(receipt_id=receipt_id)
        status = status_response.get("status")
        
        # If status is still pending, check again after more time
        if status == "pending":
            await asyncio.sleep(5)
            status_response = await receipt_client.get_receipt_status(receipt_id=receipt_id)
            status = status_response.get("status")
        
        # If QR code processing succeeded (processing or accepted), send receipt items
        if status in ("processing", "accepted"):
            line_items = status_response.get("line_items", [])
            darnitsa_products = status_response.get("darnitsa_products", [])
            
            # Build structured message with all receipt items
            if line_items:
                message_parts = ["✅ <b>Чек успішно розпізнано!</b>\n\n"]
                message_parts.append("📋 <b>Позиції в чеку:</b>\n\n")
                
                total_amount = 0
                for idx, item in enumerate(line_items, start=1):
                    name = item.get("name", "Невідомий товар")
                    quantity = item.get("quantity", 1)
                    price = float(item.get("price", 0) or 0) / 100  # Convert from kopecks to UAH
                    item_total = price * quantity
                    total_amount += item_total
                    
                    # Check if this is a Darnitsa product
                    is_darnitsa = item.get("is_darnitsa", False)
                    product_marker = "💊 " if is_darnitsa else ""
                    
                    if quantity > 1:
                        message_parts.append(f"{idx}. {product_marker}<b>{name}</b>\n")
                        message_parts.append(f"   Кількість: {quantity} шт.\n")
                        message_parts.append(f"   Ціна за одиницю: {price:.2f} грн\n")
                        message_parts.append(f"   Сума: {item_total:.2f} грн\n\n")
                    else:
                        message_parts.append(f"{idx}. {product_marker}<b>{name}</b> - {price:.2f} грн\n\n")
                
                message_parts.append(f"━━━━━━━━━━━━━━━━━━━━\n")
                message_parts.append(f"💰 <b>Загальна сума: {total_amount:.2f} грн</b>\n\n")
                
                # Add Darnitsa products info if found
                if darnitsa_products and len(darnitsa_products) > 0:
                    message_parts.append("🎉 <b>Знайдено препарат(и) Дарниця!</b>\n\n")
                    message_parts.append("✅ <b>Бонус буде нараховано!</b>\n\n")
                    message_parts.append("💳 <b>Що далі?</b>\n")
                    message_parts.append("Вам буде зараховано 1₴ на мобільний телефон протягом години після підтвердження чека.\n\n")
                    message_parts.append("⏳ Зачекайте, будь ласка. Ви отримаєте повідомлення про виплату бонусу.")
                else:
                    message_parts.append("ℹ️ <b>У вашому чеку не знайдено препаратів Дарниця</b>\n\n")
                    message_parts.append("Бонус нараховується тільки за покупку продукції Дарниця.\n\n")
                    message_parts.append("💡 <b>Порада:</b>\n")
                    message_parts.append("Переконайтеся, що на чеку є продукти Дарниця та спробуйте надіслати чек ще раз.")
                
                await bot.send_message(telegram_id, "".join(message_parts), parse_mode="HTML")
            else:
                # No items found
                await bot.send_message(
                    telegram_id,
                    "✅ <b>Чек успішно розпізнано!</b>\n\n"
                    "ℹ️ На жаль, не вдалося отримати список позицій з чека.\n\n"
                    "💡 <b>Можливі причини:</b>\n"
                    "• Низька якість фото\n"
                    "• Чек не читабельний\n"
                    "• Проблеми з розпізнаванням тексту\n\n"
                    "🔄 Спробуйте надіслати фото чека ще раз з кращою якістю.",
                    parse_mode="HTML",
                )
        # If QR code processing failed (rejected), don't send message
        elif status == "rejected":
            # Message removed per user request
            pass
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
                        "❌ <b>Помилка формату</b>\n\n"
                        "Використовуйте формат: <b>Назва товару, кількість, ціна</b>\n\n"
                        "📝 <b>Приклад:</b>\n"
                        "<code>Дарниця Цитрамон, 1, 50.00</code>\n\n"
                        "💡 Кожен товар на окремому рядку.",
                        parse_mode="HTML",
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
                        "❌ <b>Помилка формату</b>\n\n"
                        "Використовуйте формат: <b>Назва товару, кількість, ціна</b>\n\n"
                        "📝 <b>Приклад:</b>\n"
                        "<code>Дарниця Цитрамон, 1, 50.00</code>",
                        parse_mode="HTML",
                    )
                    return
            else:
                await message.answer(
                    "❌ <b>Помилка формату</b>\n\n"
                    "Використовуйте формат: <b>Назва товару, кількість, ціна</b>\n\n"
                    "📝 <b>Приклад:</b>\n"
                    "<code>Дарниця Цитрамон, 1, 50.00</code>",
                    parse_mode="HTML",
                )
                return
            
            line_items.append({
                "name": name,
                "quantity": quantity,
                "price": price,
            })
        
        if not line_items:
            await message.answer(
                "❌ <b>Не вдалося розпізнати дані</b>\n\n"
                "Перевірте формат введених даних та спробуйте ще раз.\n\n"
                "💡 <b>Правильний формат:</b>\n"
                "<code>Назва товару, кількість, ціна</code>\n\n"
                "📝 <b>Приклад:</b>\n"
                "<code>Дарниця Цитрамон, 1, 50.00</code>",
                parse_mode="HTML",
            )
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
                "✅ <b>Дані чека отримано!</b>\n\n"
                "Ваші дані будуть перевірені та нараховано кешбек.\n\n"
                "⏳ Зачекайте, будь ласка. Ви отримаєте повідомлення про результат обробки.",
                parse_mode="HTML",
            )
        except Exception as e:
            await message.answer(
                "❌ <b>Помилка при збереженні даних</b>\n\n"
                "Не вдалося зберегти дані чека.\n\n"
                "💡 <b>Що робити:</b>\n"
                "• Перевірте формат введених даних\n"
                "• Спробуйте надіслати дані ще раз\n\n"
                "Якщо проблема повторюється, зверніться до підтримки.",
                parse_mode="HTML",
            )
        return
    
    await message.answer(
        "📷 <b>Надішліть фото чека</b>\n\n"
        "Щоб отримати бонус, надішліть фото чека з продуктами Дарниця.\n\n"
        "💡 <b>Пам'ятайте:</b>\n"
        "• На чеку має бути QR код\n"
        "• Фото має бути чітким та читабельним\n"
        "• Бонус нараховується тільки за продукцію Дарниця\n\n"
        "Скористайтеся кнопкою '📸 Як надіслати чек?' для детальних інструкцій.",
        parse_mode="HTML",
    )

