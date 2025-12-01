from __future__ import annotations

import asyncio
import logging
import signal
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from libs.common import configure_logging, get_settings

from .config import BotConfig
from .handlers import build_router
from .middlewares import DependencyMiddleware
from .services import ReceiptApiClient

logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    config = BotConfig.from_settings(settings)
    
    logger.info(f"Starting bot with token: {config.token[:10]}...")
    logger.info(f"API Gateway URL: {settings.api_gateway_url}")
    
    bot = Bot(token=config.token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    receipt_client = ReceiptApiClient(base_url=settings.api_gateway_url)

    dp.include_router(build_router())
    dp.message.middleware(DependencyMiddleware(receipt_client=receipt_client))

    async def shutdown() -> None:
        logger.info("Shutting down bot...")
        await receipt_client.close()
        await bot.session.close()

    # Обработка сигналов (работает только на Unix-системах)
    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            asyncio.get_event_loop().add_signal_handler(
                sig, lambda s=sig: asyncio.create_task(shutdown())
            )
    else:
        # На Windows используем альтернативный способ
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            asyncio.create_task(shutdown())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    try:
        logger.info("Bot is starting polling...")
        await dp.start_polling(bot, skip_updates=True)
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt, shutting down...")
    except Exception as e:
        logger.error(f"Fatal error in bot: {e}", exc_info=True)
        raise
    finally:
        await shutdown()


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()

