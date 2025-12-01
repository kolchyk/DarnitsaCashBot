from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup

from libs.common.i18n import get_translator

from ..services import ReceiptApiClient

router = Router(name="commands")


@router.message(Command("start"))
async def cmd_start(message: Message, receipt_client: ReceiptApiClient):
    _ = get_translator(get_locale(message))
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=_("Share phone number"), request_contact=True)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await message.answer(_("Welcome to DarnitsaCashBot! Please share your phone number."), reply_markup=kb)
    await receipt_client.register_user(
        telegram_id=message.from_user.id,
        phone_number=message.contact.phone_number if message.contact else None,
        locale=get_locale(message),
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
        lines.append(f"- {item['status']} @ {item['uploaded_at']} (EasyPay: {item.get('easypay_reference','-')})")
    await message.answer("\n".join(lines))


@router.message(Command("change_phone"))
async def cmd_change_phone(message: Message):
    _ = get_translator(get_locale(message))
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=_("Share phone number"), request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await message.answer(_("Tap the button below to update your phone."), reply_markup=kb)


@router.message(F.contact)
async def handle_contact(message: Message, receipt_client: ReceiptApiClient):
    _ = get_translator(get_locale(message))
    await receipt_client.register_user(
        telegram_id=message.from_user.id,
        phone_number=message.contact.phone_number,
        locale=get_locale(message),
    )
    await message.answer(_("Phone number saved. Send your receipt when ready."))


def get_locale(message: Message) -> str:
    return (message.from_user.language_code or "uk")[:2]

