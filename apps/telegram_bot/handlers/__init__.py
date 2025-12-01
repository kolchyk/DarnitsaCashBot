from aiogram import Router

from . import commands, media


def build_router() -> Router:
    router = Router()
    router.include_router(commands.router)
    router.include_router(media.router)
    return router


__all__ = ["build_router"]

