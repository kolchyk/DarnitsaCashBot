from fastapi import APIRouter

from . import admin, bot, portmone


def build_router() -> APIRouter:
    router = APIRouter()
    router.include_router(bot.router, prefix="/bot", tags=["bot"])
    router.include_router(admin.router, prefix="/admin", tags=["admin"])
    router.include_router(portmone.router, prefix="/portmone", tags=["portmone"])
    return router


__all__ = ["build_router"]

