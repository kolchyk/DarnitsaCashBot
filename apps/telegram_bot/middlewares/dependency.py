from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject


class DependencyMiddleware(BaseMiddleware):
    """Injects shared dependencies into handler data dict."""

    def __init__(self, **dependencies: Any) -> None:
        super().__init__()
        self.dependencies = dependencies

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        data.update(self.dependencies)
        return await handler(event, data)

