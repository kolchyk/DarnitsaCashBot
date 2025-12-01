from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import time
import uuid

from fastapi import FastAPI, Request, Response
from prometheus_client import Counter, Histogram, generate_latest, REGISTRY
from starlette.responses import PlainTextResponse

try:
    from opentelemetry import trace
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
except ImportError:  # pragma: no cover
    trace = None
    FastAPIInstrumentor = None

from libs.common import configure_logging, get_settings
from libs.common.logging import set_correlation_id
from libs.common.notifications import NotificationService

from .background import bonus_event_listener, reminder_job
from .routes import build_router


def _get_or_create_counter(name: str, documentation: str, labelnames: list[str]) -> Counter:
    """Get existing counter or create a new one, handling module reloads."""
    try:
        # Try to create the counter - will raise ValueError if it already exists
        return Counter(name, documentation, labelnames)
    except ValueError:
        # Metric already exists, find all related collectors and unregister them
        # Prometheus creates multiple timeseries: name, name_created, and possibly name without suffix
        collectors_to_unregister = []
        for metric_name, collector in list(REGISTRY._names_to_collectors.items()):
            # Match the base name or related variants
            if metric_name == name or metric_name.startswith(f"{name}_") or metric_name == name.replace("_total", ""):
                collectors_to_unregister.append(collector)
        
        # Unregister all related collectors
        for collector in set(collectors_to_unregister):
            try:
                REGISTRY.unregister(collector)
            except KeyError:
                pass
        
        # Now create the counter again
        return Counter(name, documentation, labelnames)


def _get_or_create_histogram(
    name: str, documentation: str, labelnames: list[str], buckets: tuple
) -> Histogram:
    """Get existing histogram or create a new one, handling module reloads."""
    try:
        # Try to create the histogram - will raise ValueError if it already exists
        return Histogram(name, documentation, labelnames, buckets=buckets)
    except ValueError:
        # Metric already exists, find all related collectors and unregister them
        # Prometheus creates multiple timeseries: name, name_bucket, name_sum, name_count
        collectors_to_unregister = []
        for metric_name, collector in list(REGISTRY._names_to_collectors.items()):
            if metric_name == name or metric_name.startswith(f"{name}_"):
                collectors_to_unregister.append(collector)
        
        # Unregister all related collectors
        for collector in set(collectors_to_unregister):
            try:
                REGISTRY.unregister(collector)
            except KeyError:
                pass
        
        # Now create the histogram again
        return Histogram(name, documentation, labelnames, buckets=buckets)


REQUEST_COUNT = _get_or_create_counter(
    "api_requests_total", "Total API requests", ["method", "path", "status"]
)
REQUEST_LATENCY = _get_or_create_histogram(
    "api_request_latency_seconds",
    "API request latency",
    ["method", "path"],
    buckets=(0.1, 0.3, 1, 3, 5),
)


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
        asyncio.create_task(reminder_job(notification_service)),
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
    app.include_router(build_router())
    if FastAPIInstrumentor and settings.otel_endpoint:
        FastAPIInstrumentor.instrument_app(app)

    @app.middleware("http")
    async def tracing_middleware(request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-Id", str(uuid.uuid4()))
        set_correlation_id(correlation_id)
        request.state.correlation_id = correlation_id
        start = time.perf_counter()
        response: Response = await call_next(request)
        duration = time.perf_counter() - start
        REQUEST_COUNT.labels(request.method, request.url.path, response.status_code).inc()
        REQUEST_LATENCY.labels(request.method, request.url.path).observe(duration)
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
                "metrics": "/metrics",
                "bot": "/bot",
                "admin": "/admin",
                "portmone": "/portmone",
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

    @app.get("/metrics", tags=["system"])
    async def metrics():
        return PlainTextResponse(content=generate_latest().decode("utf-8"), media_type="text/plain")

    return app


app = create_app()


def run():
    import os
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    reload = os.environ.get("APP_ENV", "local") == "local"
    uvicorn.run("apps.api_gateway.main:app", host="0.0.0.0", port=port, reload=reload)


if __name__ == "__main__":
    run()

