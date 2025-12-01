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
            + "Вибачте, сталася помилка під час з'єднання з сервером. Будь ласка, спробуйте пізніше."
        )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "Надішліть фото чеку з продуктами Дарниця, щоб отримати бонус 1₴. "
        "Скористайтеся /history, щоб переглянути історію.",
        reply_markup=main_menu_keyboard(),
    )


@router.message(Command("menu"))
async def cmd_menu(message: Message):
    """Показать главное меню"""
    await message.answer(
        "Головне меню:",
        reply_markup=main_menu_keyboard(),
    )


@router.message(Command("history"))
async def cmd_history(message: Message, receipt_client: ReceiptApiClient):
    history = await receipt_client.fetch_history(telegram_id=message.from_user.id)
    if not history:
        await message.answer("Ще не надсилали жодного чеку.", reply_markup=main_menu_keyboard())
        return
    lines = [
        f"Останні {len(history)} чеки:",
    ]
    for item in history:
        reference = item.get("payout_reference") or "-"
        payout_status = item.get("payout_status") or "-"
        status_translated = translate_status(item["status"])
        payout_status_translated = translate_status(payout_status) if payout_status != "-" else "-"
        uploaded_at_formatted = format_datetime_uk(item["uploaded_at"])
        lines.append(
            f"- {status_translated} @ {uploaded_at_formatted} (Portmone: {reference}, статус: {payout_status_translated})"
        )
    await message.answer("\n".join(lines), reply_markup=main_menu_keyboard())


@router.message(Command("change_phone"))
async def cmd_change_phone(message: Message):
    await message.answer(phone_prompt_text(), reply_markup=contact_keyboard())


@router.message(F.text == "📋 Історія чеків")
async def handle_menu_history(message: Message, receipt_client: ReceiptApiClient):
    """Обработчик кнопки меню 'История чеков'"""
    await cmd_history(message, receipt_client)


@router.message(F.text == "ℹ️ Допомога")
async def handle_menu_help(message: Message):
    """Обработчик кнопки меню 'Помощь'"""
    await cmd_help(message)


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
            "Вітаємо в DarnitsaCashBot! 🎉\n\n"
            "Ми нараховуємо бонуси за препарати Дарниця. Потрібне фото чека.\n\n"
            f"Поділіться номером телефону, щоб ми могли надсилати поповнення 1₴ PortmoneDirect за кожен прийнятий чек. {consent}"
        )
    return (
        f"{greeting}\n\n"
        f"З поверненням! Ми вже маємо ваш номер — просто надішліть фото чека Дарниця, "
        f"щоб отримати наступний бонус 1₴. {consent}"
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
            ],
            [
                KeyboardButton(text="ℹ️ Допомога"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Надішліть фото чека або виберіть дію",
    )


def phone_prompt_text() -> str:
    return (
        "Нам потрібен підтверджений номер телефону, щоб запустити виплати PortmoneDirect. "
        "Натисніть кнопку нижче, щоб поділитися ним."
    )


def contact_saved_text() -> str:
    return (
        f"Номер збережено. Тепер можете надіслати фото чека, щоб отримати бонус 1₴. {consent_notice()}"
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

