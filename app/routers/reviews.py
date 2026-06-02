from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories import prediction_repository as pred_repo
from app.schemas.review import LlmReviewResponse
from app.services import llm_review_service
from app.services.llm_review_service import LlmGenerationError, LlmNotConfiguredError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/reviews", tags=["reviews"])


@router.get(
    "/{prediction_id}",
    response_model=LlmReviewResponse,
    name="get_review_by_prediction_id",
    operation_id="get_review_by_prediction_id",
    summary="심사 코멘트 조회·생성",
    description=(
        "`prediction_id`에 대해 저장된 **LLM 심사 코멘트**가 있으면 반환합니다. "
        "없으면 `prediction_result`와 `explanation_result`(SHAP)를 읽어 LLM으로 생성 후 "
        "`llm_review_result`에 저장하고 반환합니다.\n\n"
        "- 예측이 없으면 **404**.\n"
        "- SHAP 설명이 없으면 **400** (먼저 `POST /api/v1/explanations`).\n"
        "- `OPENAI_API_KEY` 미설정 시 **503**."
    ),
)
def get_review(
    prediction_id: Annotated[
        int,
        Path(description="예측 결과 ID(`prediction_result.id`)"),
    ],
    db: Session = Depends(get_db),
) -> LlmReviewResponse:
    try:
        row = llm_review_service.get_or_create_llm_review(db, prediction_id)
        pred = pred_repo.get_prediction_by_id(db, prediction_id)
        if pred is None:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"prediction_id={prediction_id} not found",
            )
        db.commit()
        db.refresh(row)
    except LookupError as exc:
        db.rollback()
        logger.warning("GET /api/v1/reviews/%s failed (404): %s", prediction_id, exc)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        db.rollback()
        logger.warning("GET /api/v1/reviews/%s failed (400): %s", prediction_id, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except LlmNotConfiguredError as exc:
        db.rollback()
        logger.warning("GET /api/v1/reviews/%s failed (503): %s", prediction_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except LlmGenerationError as exc:
        db.rollback()
        logger.warning("GET /api/v1/reviews/%s failed (502): %s", prediction_id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        db.rollback()
        logger.exception(
            "GET /api/v1/reviews/%s failed (unexpected)",
            prediction_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="LLM review failed",
        ) from exc

    payload = llm_review_service.review_to_response_dict(row, pred)
    return LlmReviewResponse.model_validate(payload)
