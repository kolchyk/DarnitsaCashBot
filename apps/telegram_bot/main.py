from __future__ import annotations

import asyncio
import signal

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode

from libs.common import configure_logging, get_settings

from .config import BotConfig
from .handlers import build_router
from .middlewares import DependencyMiddleware
from .services import ReceiptApiClient


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    config = BotConfig.from_settings(settings)
    bot = Bot(token=config.token, parse_mode=ParseMode.HTML)
    dp = Dispatcher()
    receipt_client = ReceiptApiClient(base_url=settings.api_gateway_url)

    dp.include_router(build_router())
    dp.message.middleware(DependencyMiddleware(receipt_client=receipt_client))

    async def shutdown() -> None:
        await receipt_client.close()
        await bot.session.close()

    for sig in (signal.SIGINT, signal.SIGTERM):
        asyncio.get_event_loop().add_signal_handler(sig, lambda: asyncio.create_task(shutdown()))

    await dp.start_polling(bot)


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()

