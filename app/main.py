from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.logging_config import configure_logging
from app.routers import health_router, predictions_router

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level_int())

    application = FastAPI(
        title="Loan Risk API",
        version="0.1.0",
        description=(
            "Lending Club 기반 대출 **연체(부실) 위험** 예측 API입니다. "
            "`loan_application_feature`의 `model_input_json`과 등록된 LightGBM 모델로 단건 예측을 수행합니다."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        openapi_tags=[
            {
                "name": "health",
                "description": "애플리케이션·데이터베이스 가동 상태 확인(헬스 체크).",
            },
            {
                "name": "predictions",
                "description": (
                    "모델 레지스트리에 등록된 학습 모델로 **단건 예측**을 수행하고, "
                    "`prediction_result`에 저장된 **예측 결과를 조회**합니다."
                ),
            },
        ],
    )

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        logger.warning(
            "Request validation failed: %s %s — %s",
            request.method,
            request.url.path,
            exc.errors(),
        )
        return JSONResponse(status_code=422, content={"detail": exc.errors()})

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        if isinstance(exc, HTTPException):
            return await http_exception_handler(request, exc)
        logger.exception(
            "Unhandled error: %s %s",
            request.method,
            request.url.path,
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    application.include_router(health_router)
    application.include_router(predictions_router)
    return application


app = create_app()
