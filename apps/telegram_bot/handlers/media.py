from __future__ import annotations

from uuid import uuid4

from aiogram import F, Router
from aiogram.types import Message

from libs.common.i18n import get_translator

from ..services import ReceiptApiClient

router = Router(name="media")


@router.message(F.photo)
async def handle_receipt_photo(message: Message, receipt_client: ReceiptApiClient):
    _ = get_translator(get_locale(message))
    photo = message.photo[-1]
    if photo.file_size and photo.file_size > 10 * 1024 * 1024:
        await message.answer(_("Receipt image exceeds 10MB. Please send a smaller file."))
        return
    file = await message.bot.get_file(photo.file_id)
    file_bytes = await message.bot.download_file(file.file_path)
    content = file_bytes.read()

    await message.answer(_("Processing your receipt..."))
    response = await receipt_client.upload_receipt(
        telegram_id=message.from_user.id,
        photo_bytes=content,
        filename=f"receipt-{uuid4()}.jpg",
        content_type="image/jpeg",
    )
    await message.answer(
        _("Receipt received. Current status: {status}").format(status=response["status"])
    )


@router.message(~F.photo & ~F.contact & ~F.text.startswith("/"))
async def fallback_handler(message: Message):
    _ = get_translator(get_locale(message))
    await message.answer(_("Please send a receipt photo or use /help for guidance."))


def get_locale(message: Message) -> str:
    return (message.from_user.language_code or "uk")[:2]

