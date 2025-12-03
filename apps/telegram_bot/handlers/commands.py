from __future__ import annotations

import logging
from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove

from libs.common.i18n import translate_status

from ..services import ReceiptApiClient

logger = logging.getLogger(__name__)

router = Router(name="commands")


@router.message(Command("start"))
async def cmd_start(message: Message, receipt_client: ReceiptApiClient):
    phone_number = None
    if message.contact and hasattr(message.contact, 'phone_number'):
        phone_number = message.contact.phone_number
    
    try:
        user_info = await receipt_client.register_user(
            telegram_id=message.from_user.id,
            phone_number=phone_number,
            locale="uk",
        )
        has_phone = bool(user_info.get("has_phone"))
        if not has_phone:
            reply_markup = contact_keyboard()
        else:
            # Показываем основное меню после успешной регистрации
            reply_markup = main_menu_keyboard()
        user_name = message.from_user.first_name or ""
        await message.answer(
            onboarding_text(require_phone=not has_phone, user_name=user_name),
            reply_markup=reply_markup,
        )
    except Exception as e:
        logger.error(f"Error in /start command: {e}", exc_info=True)
        user_name = message.from_user.first_name or ""
        greeting = f"Привіт, {user_name}! 👋" if user_name else "Привіт! 👋"
        await message.answer(
            f"{greeting}\n\n"
            + "❌ Вибачте, сталася помилка під час з'єднання з сервером.\n\n"
            + "🔄 Будь ласка, спробуйте пізніше або зверніться до підтримки."
        )


@router.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        "📖 <b>Допомога по використанню бота</b>\n\n"
        "🎯 <b>Як отримати бонус?</b>\n"
        "1️⃣ Надішліть фото чека з продуктами Дарниця\n"
        "2️⃣ Переконайтеся, що на чеку є QR код\n"
        "3️⃣ Очікуйте обробки та підтвердження\n"
        "4️⃣ Отримайте 1₴ на мобільний телефон\n\n"
        "📸 <b>Вимоги до фото:</b>\n"
        "• Чек має бути чітким та читабельним\n"
        "• QR код має бути видимим\n"
        "• Фото має бути в хорошій якості\n\n"
        "💰 <b>Система бонусів:</b>\n"
        "• 1₴ за кожен прийнятий чек з продуктами Дарниця\n"
        "• Виплата відбувається протягом години після підтвердження\n"
        "• Бонус нараховується тільки за продукцію Дарниця\n\n"
        "❓ <b>Часті питання:</b>\n"
        "• Чи можна надсилати кілька чеків? Так, без обмежень\n"
        "• Як довго обробляється чек? Зазвичай 1-2 хвилини\n"
        "• Що робити, якщо чек відхилено? Перевірте якість фото та наявність QR коду\n\n"
        "💡 <b>Команди:</b>\n"
        "/start - почати роботу з ботом\n"
        "/history - переглянути історію чеків\n"
        "/help - показати цю довідку"
    )
    await message.answer(help_text, reply_markup=main_menu_keyboard(), parse_mode="HTML")


@router.message(Command("history"))
async def cmd_history(message: Message, receipt_client: ReceiptApiClient):
    history = await receipt_client.fetch_history(telegram_id=message.from_user.id)
    if not history:
        await message.answer(
            "📋 <b>Історія чеків</b>\n\n"
            "Ви ще не надсилали жодного чека.\n\n"
            "💡 Надішліть фото чека з продуктами Дарниця, щоб отримати бонус 1₴!",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
        return
    
    # Count statistics
    accepted_count = sum(1 for item in history if item["status"] == "accepted")
    pending_count = sum(1 for item in history if item["status"] in ("pending", "processing"))
    rejected_count = sum(1 for item in history if item["status"] == "rejected")
    paid_count = sum(1 for item in history if item.get("payout_status") == "payout_success")
    
    lines = [
        f"📋 <b>Історія чеків</b>\n",
        f"Всього чеків: {len(history)}\n",
        f"✅ Прийнято: {accepted_count}",
        f"⏳ Обробляється: {pending_count}",
        f"❌ Відхилено: {rejected_count}",
        f"💰 Виплачено: {paid_count}\n",
        f"━━━━━━━━━━━━━━━━━━━━\n",
    ]
    
    for idx, item in enumerate(history, 1):
        payout_status = item.get("payout_status") or "-"
        status_translated = translate_status(item["status"])
        payout_status_translated = translate_status(payout_status) if payout_status != "-" else ""
        uploaded_at_formatted = format_datetime_uk(item["uploaded_at"])
        
        line = f"<b>{idx}.</b> {status_translated}\n"
        line += f"   📅 {uploaded_at_formatted}\n"
        
        if payout_status_translated:
            line += f"   {payout_status_translated}\n"
        
        lines.append(line)
        if idx < len(history):
            lines.append("")
    
    await message.answer("\n".join(lines), reply_markup=main_menu_keyboard(), parse_mode="HTML")


@router.message(Command("change_phone"))
async def cmd_change_phone(message: Message):
    await message.answer(phone_prompt_text(), reply_markup=contact_keyboard())


@router.message(F.text == "📋 Історія чеків")
async def handle_menu_history(message: Message, receipt_client: ReceiptApiClient):
    """Обработчик кнопки меню 'История чеков'"""
    await cmd_history(message, receipt_client)


@router.message(F.text == "📊 Статистика")
async def handle_menu_statistics(message: Message, receipt_client: ReceiptApiClient):
    """Обработчик кнопки меню 'Статистика'"""
    try:
        stats = await receipt_client.get_statistics()
        stats_text = (
            "📊 <b>Загальна статистика системи</b>\n\n"
            f"👥 Користувачів у системі: {stats.get('user_count', 0):,}\n"
            f"🧾 Всього чеків оброблено: {stats.get('receipt_count', 0):,}\n"
            f"💰 Всього бонусів нараховано: {stats.get('bonus_count', 0):,}\n\n"
            "💡 Використайте кнопку '💰 Мої бонуси' для перегляду вашої персональної статистики."
        )
        await message.answer(stats_text, reply_markup=main_menu_keyboard(), parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error fetching statistics: {e}", exc_info=True)
        await message.answer(
            "❌ Вибачте, не вдалося отримати статистику. Спробуйте пізніше.",
            reply_markup=main_menu_keyboard(),
        )


@router.message(F.text == "ℹ️ Допомога")
async def handle_menu_help(message: Message):
    """Обработчик кнопки меню 'Помощь'"""
    await cmd_help(message)


@router.message(F.text == "📸 Як надіслати чек?")
async def handle_menu_how_to_send(message: Message):
    """Обработчик кнопки меню 'Як надіслати чек?'"""
    how_to_text = (
        "📸 <b>Як правильно надіслати чек?</b>\n\n"
        "1️⃣ <b>Зробіть фото чека</b>\n"
        "• Використовуйте камеру телефону\n"
        "• Переконайтеся, що чек чіткий та читабельний\n"
        "• Уникайте затемнених або розмитих фото\n\n"
        "2️⃣ <b>Перевірте QR код</b>\n"
        "• QR код має бути видимим на фото\n"
        "• Переконайтеся, що QR код не пошкоджений\n"
        "• QR код зазвичай розташований у верхній або нижній частині чека\n\n"
        "3️⃣ <b>Надішліть фото</b>\n"
        "• Просто надішліть фото чека в чат\n"
        "• Дочекайтеся підтвердження отримання\n"
        "• Обробка зазвичай займає 1-2 хвилини\n\n"
        "✅ <b>Після обробки ви отримаєте:</b>\n"
        "• Список всіх позицій з чека\n"
        "• Інформацію про знайдені продукти Дарниця\n"
        "• Підтвердження нарахування бонусу\n\n"
        "💡 <b>Поради:</b>\n"
        "• Робіть фото при хорошому освітленні\n"
        "• Переконайтеся, що весь чек поміщається в кадр\n"
        "• Не надсилайте скріншоти - тільки фото оригінального чека"
    )
    await message.answer(how_to_text, reply_markup=main_menu_keyboard(), parse_mode="HTML")


@router.message(F.text == "💰 Мої бонуси")
async def handle_menu_my_bonuses(message: Message, receipt_client: ReceiptApiClient):
    """Обработчик кнопки меню 'Мої бонуси'"""
    try:
        history = await receipt_client.fetch_history(telegram_id=message.from_user.id)
        
        if not history:
            await message.answer(
                "💰 <b>Мої бонуси</b>\n\n"
                "Ви ще не надсилали жодного чека.\n\n"
                "💡 Надішліть фото чека з продуктами Дарниця, щоб отримати перший бонус 1₴!",
                reply_markup=main_menu_keyboard(),
                parse_mode="HTML",
            )
            return
        
        # Calculate user statistics
        total_receipts = len(history)
        accepted_receipts = sum(1 for item in history if item["status"] == "accepted")
        paid_bonuses = sum(1 for item in history if item.get("payout_status") == "payout_success")
        pending_bonuses = sum(1 for item in history if item.get("payout_status") == "payout_pending")
        total_bonus_amount = paid_bonuses * 1  # 1₴ per receipt
        
        bonus_text = (
            "💰 <b>Моя статистика</b>\n\n"
            f"📊 <b>Чеки:</b>\n"
            f"• Всього надіслано: {total_receipts}\n"
            f"• Прийнято: {accepted_receipts}\n"
            f"• Очікує обробки: {sum(1 for item in history if item['status'] in ('pending', 'processing'))}\n\n"
            f"💵 <b>Бонуси:</b>\n"
            f"• Виплачено: {paid_bonuses} × 1₴ = {total_bonus_amount}₴\n"
            f"• Очікує виплати: {pending_bonuses}\n"
            f"• Можливих бонусів: {accepted_receipts - paid_bonuses - pending_bonuses}\n\n"
        )
        
        if paid_bonuses > 0:
            bonus_text += f"🎉 Вітаємо! Ви вже отримали {total_bonus_amount}₴ бонусів!\n\n"
        
        if accepted_receipts > paid_bonuses + pending_bonuses:
            bonus_text += "⏳ Деякі бонуси ще обробляються. Виплата відбувається протягом години після підтвердження чека.\n\n"
        
        bonus_text += "💡 Продовжуйте надсилати чеки з продуктами Дарниця, щоб отримувати більше бонусів!"
        
        await message.answer(bonus_text, reply_markup=main_menu_keyboard(), parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error fetching user bonuses: {e}", exc_info=True)
        await message.answer(
            "❌ Вибачте, не вдалося отримати статистику бонусів. Спробуйте пізніше.",
            reply_markup=main_menu_keyboard(),
        )


@router.message(F.contact)
async def handle_contact(message: Message, receipt_client: ReceiptApiClient):
    user_info = await receipt_client.register_user(
        telegram_id=message.from_user.id,
        phone_number=message.contact.phone_number,
        locale="uk",
    )
    if user_info.get("has_phone"):
        await message.answer(contact_saved_text(), reply_markup=main_menu_keyboard())
        return
    await message.answer(phone_prompt_text(), reply_markup=contact_keyboard())


def onboarding_text(*, require_phone: bool, user_name: str = "") -> str:
    consent = consent_notice()
    greeting = f"Привіт, {user_name}! 👋" if user_name else "Привіт! 👋"
    
    if require_phone:
        return (
            f"{greeting}\n\n"
            "🎉 <b>Вітаємо в DarnitsaCashBot!</b>\n\n"
            "💰 <b>Отримуйте бонуси за покупки Дарниця!</b>\n\n"
            "📸 <b>Як це працює:</b>\n"
            "1. Надішліть фото чека з продуктами Дарниця\n"
            "2. Переконайтеся, що на чеку є QR код\n"
            "3. Отримайте 1₴ на мобільний телефон\n\n"
            "✅ <b>Що потрібно:</b>\n"
            "• Чітке фото чека\n"
            "• Видимий QR код\n"
            "• Продукти Дарниця в чеку\n\n"
            f"📱 <b>Наступний крок:</b>\n"
            f"Поділіться номером телефону, щоб ми могли надсилати поповнення 1₴ за кожен прийнятий чек.\n\n"
            f"{consent}"
        )
    return (
        f"{greeting}\n\n"
        f"🎉 <b>З поверненням!</b>\n\n"
        f"Ми вже маємо ваш номер телефону.\n\n"
        f"📸 <b>Що далі?</b>\n"
        f"Просто надішліть фото чека з продуктами Дарниця, щоб отримати наступний бонус 1₴.\n\n"
        f"💡 <b>Пам'ятайте:</b>\n"
        f"• Переконайтеся, що на чеку є QR код\n"
        f"• Фото має бути чітким та читабельним\n"
        f"• Бонус нараховується тільки за продукцію Дарниця\n\n"
        f"{consent}"
    )


def contact_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для запроса контакта"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Поділитися номером телефону", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Главное меню бота - постоянная клавиатура внизу экрана"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📋 Історія чеків"),
                KeyboardButton(text="💰 Мої бонуси"),
            ],
            [
                KeyboardButton(text="📸 Як надіслати чек?"),
                KeyboardButton(text="ℹ️ Допомога"),
            ],
            [
                KeyboardButton(text="📊 Статистика"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="📷 Надішліть фото чека або виберіть дію з меню",
    )


def phone_prompt_text() -> str:
    return (
        "📱 <b>Потрібен номер телефону</b>\n\n"
        "Для виплати бонусів нам потрібен ваш номер телефону.\n\n"
        "💡 <b>Навіщо це потрібно?</b>\n"
        "Ми надсилаємо поповнення 1₴ безпосередньо на ваш мобільний телефон після підтвердження чека.\n\n"
        "🔒 <b>Безпека:</b>\n"
        "Ваш номер телефону зберігається в зашифрованому вигляді та використовується тільки для виплати бонусів.\n\n"
        "👇 Натисніть кнопку нижче, щоб поділитися номером телефону."
    )


def contact_saved_text() -> str:
    return (
        "✅ <b>Номер телефону збережено!</b>\n\n"
        "🎉 Чудово! Тепер ви готові отримувати бонуси.\n\n"
        "📸 <b>Що далі?</b>\n"
        "Надішліть фото чека з продуктами Дарниця, щоб отримати бонус 1₴.\n\n"
        "💡 <b>Пам'ятайте:</b>\n"
        "• Переконайтеся, що на чеку є QR код\n"
        "• Фото має бути чітким та читабельним\n"
        "• Бонус нараховується тільки за продукцію Дарниця\n\n"
        f"{consent_notice()}"
    )


def consent_notice() -> str:
    return "Поділяючи свої контактні дані, ви погоджуєтеся з умовами акції та політикою конфіденційності Darnitsa."


def format_datetime_uk(dt_str: str) -> str:
    """Format datetime string to Ukrainian format: DD.MM.YYYY, HH:MM"""
    try:
        # Parse ISO format datetime string
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        # Format as DD.MM.YYYY, HH:MM
        return dt.strftime("%d.%m.%Y, %H:%M")
    except (ValueError, AttributeError):
        # Fallback to original string if parsing fails
        return dt_str

