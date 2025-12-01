from aiogram import Router

from . import commands, media

router = Router()
router.include_router(commands.router)
router.include_router(media.router)

__all__ = ["router"]

