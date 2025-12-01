from __future__ import annotations

import asyncio
import time
import uuid

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, generate_latest
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

REQUEST_COUNT = Counter("api_requests_total", "Total API requests", ["method", "path", "status"])
REQUEST_LATENCY = Histogram(
    "api_request_latency_seconds", "API request latency", ["method", "path"], buckets=(0.1, 0.3, 1, 3, 5)
)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(title="DarnitsaCashBot API", version="0.1.0")
    app.include_router(build_router())
    if FastAPIInstrumentor and settings.otel_endpoint:
        FastAPIInstrumentor.instrument_app(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

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

    @app.get("/healthz", tags=["system"])
    async def health():
        return {"status": "ok"}

    @app.get("/metrics", tags=["system"])
    async def metrics():
        return PlainTextResponse(content=generate_latest().decode("utf-8"), media_type="text/plain")

    @app.on_event("startup")
    async def startup_event():
        notification_service = NotificationService(settings)
        app.state.notification_service = notification_service
        app.state.background_tasks = [
            asyncio.create_task(bonus_event_listener(notification_service)),
            asyncio.create_task(reminder_job(notification_service)),
        ]

    @app.on_event("shutdown")
    async def shutdown_event():
        for task in getattr(app.state, "background_tasks", []):
            task.cancel()
        await asyncio.gather(*getattr(app.state, "background_tasks", []), return_exceptions=True)
        notification_service: NotificationService | None = getattr(app.state, "notification_service", None)
        if notification_service:
            await notification_service.bot.session.close()

    return app


app = create_app()


def run():
    import uvicorn

    uvicorn.run("apps.api_gateway.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    run()

