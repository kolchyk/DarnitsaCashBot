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
    error_msg = str(exc)
    error_type = type(exc).__name__
    
    logger.error(
        f"Database error: error_type={error_type}, error={error_msg}",
        exc_info=True,
    )
    
    # Determine error type and appropriate response
    if isinstance(exc, IntegrityError):
        # Check if it's a unique constraint violation
        if "unique" in error_msg.lower() or "duplicate" in error_msg.lower():
            # Extract telegram_id from request if possible
            try:
                payload = await request.json()
                telegram_id = payload.get("telegram_id")
                if telegram_id:
                    raise UserAlreadyExistsError(telegram_id)
            except Exception:
                pass
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={"detail": "Resource already exists"},
            )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "Database constraint violation"},
        )
    
    # Check for connection errors
    if "connection" in error_msg.lower() or "connect" in error_msg.lower():
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "Database connection issue"},
        )
    
    # Check for schema errors
    if "relation" in error_msg.lower() or "table" in error_msg.lower() or "does not exist" in error_msg.lower():
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Table or relation does not exist (migrations may be needed)"},
        )
    
    # Generic database error
    detail_msg = f"Database error occurred: {error_type}"
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": detail_msg},
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

