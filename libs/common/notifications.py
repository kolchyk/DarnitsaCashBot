from __future__ import annotations

from typing import Iterable

from aiogram import Bot
from aiogram.types import BufferedInputFile

from libs.common import AppSettings, get_settings


class NotificationService:
    def __init__(self, settings: AppSettings | None = None, bot: Bot | None = None) -> None:
        self.settings = settings or get_settings()
        self.bot = bot or Bot(self.settings.telegram_bot_token)

    async def send_message(self, chat_id: int, text: str, buttons: Iterable[str] | None = None):
        reply_markup = None
        if buttons:
            from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

            reply_markup = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text=btn, callback_data=btn)] for btn in buttons]
            )
        await self.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)

    async def send_photo(self, chat_id: int, data: bytes, caption: str | None = None):
        await self.bot.send_photo(chat_id=chat_id, photo=BufferedInputFile(data, filename="receipt.jpg"), caption=caption)

