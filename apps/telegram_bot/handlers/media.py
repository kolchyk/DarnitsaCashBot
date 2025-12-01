from __future__ import annotations

from uuid import uuid4

from aiogram import F, Router
from aiogram.types import Message

from libs.common.i18n import translate_status

from ..services import ReceiptApiClient

router = Router(name="media")


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
    status_translated = translate_status(response["receipt"]["status"])
    await message.answer(
        f"Чек отримано. Виплата PortmoneDirect почнеться після підтвердження. Поточний статус: {status_translated}"
    )


@router.message(~F.photo & ~F.contact & ~F.text.startswith("/"))
async def fallback_handler(message: Message):
    await message.answer("Надішліть фото чека або скористайтеся /help для інструкцій.")

