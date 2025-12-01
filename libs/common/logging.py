from __future__ import annotations

import sys
from contextvars import ContextVar
from typing import Any

from loguru import logger

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def set_correlation_id(value: str | None) -> None:
    _correlation_id.set(value)


def get_correlation_id() -> str | None:
    return _correlation_id.get()


def configure_logging(level: str = "INFO") -> None:
    logger.remove()
    logger.add(
        sys.stdout,
        level=level,
        serialize=False,
        enqueue=True,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | {level} | {message} | {extra}",
    )


def log_extra() -> dict[str, Any]:
    cid = get_correlation_id()
    return {"correlation_id": cid} if cid else {}

