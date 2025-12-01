from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Awaitable, Callable

import asyncio


class BackgroundScheduler:
    def __init__(self) -> None:
        self.tasks: list[asyncio.Task] = []

    def schedule(self, coro_factory: Callable[[], Awaitable[None]]) -> None:
        task = asyncio.create_task(coro_factory())
        self.tasks.append(task)

    async def close(self) -> None:
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)


@asynccontextmanager
async def scheduler_context():
    scheduler = BackgroundScheduler()
    try:
        yield scheduler
    finally:
        await scheduler.close()

