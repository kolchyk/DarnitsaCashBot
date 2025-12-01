from __future__ import annotations

from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject


class DependencyMiddleware(BaseMiddleware):
    """Injects shared dependencies into handler data dict."""

    def __init__(self, **dependencies: Any) -> None:
        super().__init__()
        self.dependencies = dependencies

    async def __call__(self, handler: Any, event: TelegramObject, data: dict[str, Any]) -> Any:
        data.update(self.dependencies)
        return await handler(event, data)

