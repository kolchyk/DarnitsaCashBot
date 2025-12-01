"""Custom exceptions for API Gateway."""

from __future__ import annotations


class UserRegistrationError(Exception):
    """Base exception for user registration errors."""

    def __init__(self, message: str, telegram_id: int | None = None) -> None:
        super().__init__(message)
        self.telegram_id = telegram_id


class UserAlreadyExistsError(UserRegistrationError):
    """Raised when user with given telegram_id already exists."""

    def __init__(self, telegram_id: int) -> None:
        super().__init__(f"User with telegram_id {telegram_id} already exists", telegram_id)


class EncryptionError(UserRegistrationError):
    """Raised when encryption/decryption fails."""

    pass


class DatabaseConnectionError(Exception):
    """Raised when database connection fails."""

    pass


class DatabaseSchemaError(Exception):
    """Raised when database schema issues occur (missing tables, etc.)."""

    pass

