from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from typing import Any

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def set_correlation_id(value: str | None) -> None:
    _correlation_id.set(value)


def get_correlation_id() -> str | None:
    return _correlation_id.get()


def configure_logging(level: str = "INFO") -> None:
    """Configure standard logging to output to stdout."""
    # Configure standard logging module to output to stdout
    # This ensures all logging.getLogger() calls work properly
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()
    
    # Create a stream handler that outputs to stdout
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Use a simple format
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    
    root_logger.addHandler(handler)


def log_extra() -> dict[str, Any]:
    cid = get_correlation_id()
    return {"correlation_id": cid} if cid else {}

