from __future__ import annotations

from contextlib import asynccontextmanager
import uuid

from fastapi import FastAPI, Request, Response


from libs.common import configure_logging, get_settings
from libs.common.logging import set_correlation_id
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
    
    # Startup
    # Check database connection
    try:
        from libs.data.database import async_session_factory
        from sqlalchemy import text
        async with async_session_factory() as session:
            # Try a simple query to verify connection
            await session.execute(text("SELECT 1"))
            logger.info("Database connection verified successfully")
    except ImportError as e:
        logger.error(f"Failed to import database module: {e}", exc_info=True)
        logger.warning("Application will start but database operations may fail")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}", exc_info=True)
        logger.warning("Application will start but database operations may fail")
    
    yield


def create_app() -> FastAPI:
    try:
        settings = get_settings()
    except Exception as e:
        import logging
        # Configure basic logging before settings are available
        logging.basicConfig(
            level=logging.ERROR,
            format="%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to load settings: {e}", exc_info=True)
        logger.error("This is usually caused by missing required environment variables.")
        logger.error("Required variables include: TELEGRAM_BOT_TOKEN, ENCRYPTION_SECRET")
        # Re-raise to be caught by module-level handler
        raise
    
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


# Create app at module level, but handle errors gracefully
try:
    app = create_app()
except Exception as e:
    import logging
    import sys
    # Configure basic logging before app is created
    logging.basicConfig(
        level=logging.ERROR,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    logger = logging.getLogger(__name__)
    logger.error(f"Failed to create app: {e}", exc_info=True)
    logger.error("Application cannot start. Please check your configuration.")
    # Create a minimal app that returns an error for all requests
    app = FastAPI(title="DarnitsaCashBot API - Error State")
    
    @app.get("/")
    @app.post("/")
    @app.get("/{path:path}")
    @app.post("/{path:path}")
    async def error_handler():
        return {"error": "Application failed to start", "detail": str(e)}, 503


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

