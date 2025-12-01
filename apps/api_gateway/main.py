from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import uuid

from fastapi import FastAPI, Request, Response


from libs.common import configure_logging, get_settings
from libs.common.logging import set_correlation_id
from libs.common.notifications import NotificationService

from .background import bonus_event_listener
from .exception_handlers import (
    database_connection_error_handler,
    database_error_handler,
    database_schema_error_handler,
    user_registration_error_handler,
)
from .exceptions import (
    DatabaseConnectionError,
    DatabaseSchemaError,
    UserAlreadyExistsError,
    UserRegistrationError,
)
from .routes import router as api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    import logging
    logger = logging.getLogger(__name__)
    
    settings = get_settings()
    # Startup
    # Check database connection
    try:
        from libs.data.database import get_async_session
        from sqlalchemy import text
        async for session in get_async_session():
            # Try a simple query to verify connection
            await session.execute(text("SELECT 1"))
            logger.info("Database connection verified successfully")
            break
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}", exc_info=True)
        logger.warning("Application will start but database operations may fail")
    
    notification_service = NotificationService(settings)
    app.state.notification_service = notification_service
    app.state.background_tasks = [
        asyncio.create_task(bonus_event_listener(notification_service)),
    ]
    
    yield
    
    # Shutdown
    for task in getattr(app.state, "background_tasks", []):
        task.cancel()
    await asyncio.gather(*getattr(app.state, "background_tasks", []), return_exceptions=True)
    notification_service: NotificationService | None = getattr(app.state, "notification_service", None)
    if notification_service:
        await notification_service.bot.session.close()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(title="DarnitsaCashBot API", version="0.1.0", lifespan=lifespan)
    
    # Register exception handlers
    app.add_exception_handler(UserRegistrationError, user_registration_error_handler)
    app.add_exception_handler(UserAlreadyExistsError, user_registration_error_handler)
    app.add_exception_handler(DatabaseConnectionError, database_connection_error_handler)
    app.add_exception_handler(DatabaseSchemaError, database_schema_error_handler)
    from sqlalchemy.exc import SQLAlchemyError
    app.add_exception_handler(SQLAlchemyError, database_error_handler)
    
    app.include_router(api_router)

    @app.middleware("http")
    async def tracing_middleware(request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-Id", str(uuid.uuid4()))
        set_correlation_id(correlation_id)
        request.state.correlation_id = correlation_id
        response: Response = await call_next(request)
        response.headers["X-Correlation-Id"] = correlation_id
        return response

    @app.get("/", tags=["system"])
    async def root():
        return {
            "name": "DarnitsaCashBot API",
            "version": "0.1.0",
            "status": "running",
            "endpoints": {
                "health": "/healthz",
                "bot": "/bot",
                # "portmone": "/portmone",  # Temporarily disabled
                "docs": "/docs",
                "openapi": "/openapi.json"
            }
        }

    @app.get("/healthz", tags=["system"])
    async def health():
        """Health check endpoint that verifies database connectivity."""
        from libs.data.database import get_async_session
        from sqlalchemy import text
        
        db_status = "ok"
        try:
            async for session in get_async_session():
                await session.execute(text("SELECT 1"))
                break
        except Exception as e:
            db_status = f"error: {str(e)}"
        
        return {
            "status": "ok" if db_status == "ok" else "degraded",
            "database": db_status
        }

    return app


app = create_app()


def run():
    import os
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    app_env = os.environ.get("APP_ENV", "").lower()
    reload = app_env == "local"
    # Always use import string format - required for workers/reload mode
    target_app = "apps.api_gateway.main:app"
    uvicorn.run(target_app, host="0.0.0.0", port=port, reload=reload)


if __name__ == "__main__":
    run()

