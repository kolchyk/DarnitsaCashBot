from fastapi import APIRouter

from . import bot

router = APIRouter()
router.include_router(bot.router, prefix="/bot", tags=["bot"])

__all__ = ["router"]

