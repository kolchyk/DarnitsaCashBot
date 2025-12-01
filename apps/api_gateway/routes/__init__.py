from fastapi import APIRouter

from . import admin, bot, portmone

router = APIRouter()
router.include_router(bot.router, prefix="/bot", tags=["bot"])
router.include_router(admin.router, prefix="/admin", tags=["admin"])
router.include_router(portmone.router, prefix="/portmone", tags=["portmone"])

__all__ = ["router"]

