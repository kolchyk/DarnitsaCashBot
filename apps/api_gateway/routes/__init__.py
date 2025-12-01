from fastapi import APIRouter

from . import admin, bot  # portmone temporarily disabled
# from . import portmone

router = APIRouter()
router.include_router(bot.router, prefix="/bot", tags=["bot"])
router.include_router(admin.router, prefix="/admin", tags=["admin"])
# router.include_router(portmone.router, prefix="/portmone", tags=["portmone"])  # Temporarily disabled

__all__ = ["router"]

