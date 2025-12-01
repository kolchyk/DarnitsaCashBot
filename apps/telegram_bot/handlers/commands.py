from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove

from libs.common.i18n import get_translator

from ..services import ReceiptApiClient

logger = logging.getLogger(__name__)

router = Router(name="commands")


@router.message(Command("start"))
async def cmd_start(message: Message, receipt_client: ReceiptApiClient):
    locale = get_locale(message)
    _ = get_translator(locale)
    phone_number = None
    if message.contact and hasattr(message.contact, 'phone_number'):
        phone_number = message.contact.phone_number
    
    try:
        user_info = await receipt_client.register_user(
            telegram_id=message.from_user.id,
            phone_number=phone_number,
            locale=locale,
        )
        has_phone = bool(user_info.get("has_phone"))
        reply_markup = contact_keyboard(_) if not has_phone else ReplyKeyboardRemove()
        user_name = message.from_user.first_name or ""
        await message.answer(
            onboarding_text(_, require_phone=not has_phone, user_name=user_name),
            reply_markup=reply_markup,
        )
    except Exception as e:
        logger.error(f"Error in /start command: {e}", exc_info=True)
        user_name = message.from_user.first_name or ""
        greeting = _("Hello, {name}! 👋").format(name=user_name) if user_name else _("Hello! 👋")
        await message.answer(
            f"{greeting}\n\n"
            + _("Sorry, there was an error connecting to the server. Please try again later.")
        )


@router.message(Command("help"))
async def cmd_help(message: Message):
    _ = get_translator(get_locale(message))
    await message.answer(
        _(
            "Send a photo of a Darnitsa receipt to receive a 1₴ top-up. "
            "Use /history to see your past submissions or /change_phone to update your number."
        )
    )


@router.message(Command("history"))
async def cmd_history(message: Message, receipt_client: ReceiptApiClient):
    _ = get_translator(get_locale(message))
    history = await receipt_client.fetch_history(telegram_id=message.from_user.id)
    if not history:
        await message.answer(_("No receipts submitted yet."))
        return
    lines = [
        _("Last {count} receipts:").format(count=len(history)),
    ]
    for item in history:
        reference = item.get("payout_reference") or "-"
        payout_status = item.get("payout_status") or "-"
        lines.append(
            _(
                "- {status} @ {uploaded_at} (Portmone bill: {reference}, payout: {payout_status})"
            ).format(
                status=item["status"],
                uploaded_at=item["uploaded_at"],
                reference=reference,
                payout_status=payout_status,
            )
        )
    await message.answer("\n".join(lines))


@router.message(Command("change_phone"))
async def cmd_change_phone(message: Message):
    locale = get_locale(message)
    _ = get_translator(locale)
    await message.answer(phone_prompt_text(_), reply_markup=contact_keyboard(_))


@router.message(F.contact)
async def handle_contact(message: Message, receipt_client: ReceiptApiClient):
    locale = get_locale(message)
    _ = get_translator(locale)
    user_info = await receipt_client.register_user(
        telegram_id=message.from_user.id,
        phone_number=message.contact.phone_number,
        locale=locale,
    )
    if user_info.get("has_phone"):
        await message.answer(contact_saved_text(_), reply_markup=ReplyKeyboardRemove())
        return
    await message.answer(phone_prompt_text(_), reply_markup=contact_keyboard(_))


def get_locale(message: Message) -> str:
    return (message.from_user.language_code or "uk")[:2]


def onboarding_text(_, *, require_phone: bool, user_name: str = "") -> str:
    consent = consent_notice(_)
    greeting = _("Hello, {name}! 👋").format(name=user_name) if user_name else _("Hello! 👋")
    
    if require_phone:
        return _(
            "{greeting}\n\n"
            "Welcome to DarnitsaCashBot! 🎉\n\n"
            "Share your phone number so we can send 1₴ PortmoneDirect top-ups for each approved receipt. {consent}"
        ).format(greeting=greeting, consent=consent)
    return _(
        "{greeting}\n\n"
        "Welcome back! We already have your phone number—just send a Darnitsa receipt photo to receive your next 1₴ top-up. {consent}"
    ).format(greeting=greeting, consent=consent)


def contact_keyboard(_) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=_("Share phone number"), request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def phone_prompt_text(_) -> str:
    return _(
        "We need your verified phone number to trigger PortmoneDirect payouts. Tap the button below to share it."
    )


def contact_saved_text(_) -> str:
    return _(
        "Phone number saved. You can now send a receipt photo to get your 1₴ top-up. {consent}"
    ).format(consent=consent_notice(_))


def consent_notice(_) -> str:
    return _("By sharing your contact you agree to the promo terms and privacy policy of Darnitsa.")

