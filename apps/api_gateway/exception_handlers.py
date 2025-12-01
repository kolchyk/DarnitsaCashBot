"""Exception handlers for API Gateway."""

from __future__ import annotations

import logging

from fastapi import Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .exceptions import (
    DatabaseConnectionError,
    DatabaseSchemaError,
    EncryptionError,
    UserAlreadyExistsError,
    UserRegistrationError,
)

logger = logging.getLogger(__name__)


async def user_registration_error_handler(request: Request, exc: UserRegistrationError) -> JSONResponse:
    """Handle user registration errors."""
    if isinstance(exc, UserAlreadyExistsError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc)},
        )
    if isinstance(exc, EncryptionError):
        logger.error(
            f"Encryption error during user registration: telegram_id={exc.telegram_id}, error={str(exc)}",
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error during user registration"},
        )
    logger.error(
        f"User registration error: telegram_id={exc.telegram_id}, error={str(exc)}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


async def database_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Handle database errors."""
    logger.error(f"Database error: {type(exc).__name__}: {str(exc)}", exc_info=True)
    
    # Handle integrity constraint violations (unique, foreign key, etc.)
    if isinstance(exc, IntegrityError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": "Database constraint violation"},
        )
    
    # Generic database error
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Database error occurred"},
    )


async def database_connection_error_handler(request: Request, exc: DatabaseConnectionError) -> JSONResponse:
    """Handle database connection errors."""
    logger.error(f"Database connection error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Database service temporarily unavailable"},
    )


async def database_schema_error_handler(request: Request, exc: DatabaseSchemaError) -> JSONResponse:
    """Handle database schema errors."""
    logger.error(f"Database schema error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Database schema error (migrations may be needed)"},
    )

