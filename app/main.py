from __future__ import annotations

from fastapi import FastAPI

from app.routers import health_router


def create_app() -> FastAPI:
    application = FastAPI(
        title="Loan Risk API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    application.include_router(health_router)
    return application


app = create_app()
