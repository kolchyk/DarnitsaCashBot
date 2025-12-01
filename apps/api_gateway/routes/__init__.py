from fastapi import APIRouter

from . import bot, admin


def build_router() -> APIRouter:
    router = APIRouter()
    router.include_router(bot.router, prefix="/bot", tags=["bot"])
    router.include_router(admin.router, prefix="/admin", tags=["admin"])
    return router


__all__ = ["build_router"]

