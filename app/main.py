from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.logging_config import configure_logging
from app.core.openapi_cache_middleware import DisableOpenAPICacheMiddleware
from app.routers import (
    decisions_router,
    explanations_router,
    health_router,
    predictions_router,
    reviews_router,
)

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
            {
                "name": "decisions",
                "description": (
                    "**risk_score** 구간과 **정책 룰**을 적용해 승인/심사/거절 형태의 "
                    "**final_decision**을 저장·조회합니다."
                ),
            },
            {
                "name": "explanations",
                "description": (
                    "LightGBM 예측에 대해 **SHAP(TreeExplainer)** 으로 주요 위험 요인을 계산하고 "
                    "`explanation_result`에 저장·조회합니다."
                ),
            },
            {
                "name": "reviews",
                "description": (
                    "예측·SHAP 요약을 바탕으로 **LLM 심사 코멘트**(한국어)를 생성·저장하고 "
                    "`llm_review_result`에서 조회합니다."
                ),
            },
        ],
    )

    @application.exception_handler(HTTPException)
    async def logging_http_exception_handler(
        request: Request,
        exc: HTTPException,
    ) -> JSONResponse:
        """라우터에서 올린 HTTPException: 5xx는 app.main에 ERROR로 남김."""
        if exc.status_code >= 500:
            logger.error(
                "HTTP %s %s — %s",
                request.method,
                request.url.path,
                exc.detail,
            )
        return await http_exception_handler(request, exc)

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

    @application.exception_handler(ResponseValidationError)
    async def response_validation_exception_handler(
        request: Request,
        exc: ResponseValidationError,
    ) -> JSONResponse:
        logger.error(
            "Response validation failed: %s %s — %s",
            request.method,
            request.url.path,
            exc.errors(),
            exc_info=exc,
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
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
    application.include_router(decisions_router)
    application.include_router(explanations_router)
    application.include_router(reviews_router)

    # OpenAPI / Swagger / ReDoc: 브라우저 캐시로 구 스펙이 남지 않도록
    application.add_middleware(DisableOpenAPICacheMiddleware)

    return application


app = create_app()
