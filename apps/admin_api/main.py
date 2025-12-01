from fastapi import FastAPI

from libs.common import configure_logging, get_settings

from apps.api_gateway.routes.admin import router as admin_router


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(title="DarnitsaCashBot Admin API")
    app.include_router(admin_router, prefix="/admin", tags=["admin"])
    return app


app = create_app()


def run():
    import uvicorn

    uvicorn.run("apps.admin_api.main:app", host="0.0.0.0", port=8100, reload=True)


if __name__ == "__main__":
    run()

