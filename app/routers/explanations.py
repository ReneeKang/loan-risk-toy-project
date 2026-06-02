from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.tables import ExplanationResult
from app.repositories import explanation_repository as expl_repo
from app.repositories import prediction_repository as pred_repo
from app.schemas.explanation import (
    ExplanationCreateRequest,
    ExplanationFactorItem,
    ExplanationListResponse,
)
from app.services import explanation_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/explanations", tags=["explanations"])


def _list_response_from_db(
    *,
    prediction_id: int,
    application_id: str,
    rows: list[ExplanationResult],
) -> ExplanationListResponse:
    factors = [
        ExplanationFactorItem.model_validate(explanation_service.factor_item_from_row(r))
        for r in rows
    ]
    return ExplanationListResponse(
        prediction_id=prediction_id,
        application_id=application_id,
        factors=factors,
    )


@router.post(
    "",
    response_model=ExplanationListResponse,
    status_code=status.HTTP_201_CREATED,
    summary="SHAP 설명 계산 및 저장",
    description=(
        "`application_id`와 `model_registry.model_version`으로 **최신** `prediction_result`를 찾고, "
        "같은 피처 행의 `model_input_json`과 등록된 LightGBM 모델로 SHAP(TreeExplainer)을 계산합니다. "
        "상위 3~5개 피처를 `explanation_result`에 저장합니다(동일 `prediction_id` 기존 행은 대체).\n\n"
        "먼저 `POST /api/v1/predictions`로 예측을 저장해야 합니다."
    ),
)
def create_explanation(
    body: ExplanationCreateRequest,
    db: Session = Depends(get_db),
) -> ExplanationListResponse:
    try:
        pred, rows = explanation_service.run_explanation_and_persist(
            db,
            application_id=body.application_id.strip(),
            model_version=body.model_version.strip(),
        )
        db.commit()
        db.refresh(pred)
        return _list_response_from_db(
            prediction_id=int(pred.id),
            application_id=pred.application_id,
            rows=rows,
        )
    except LookupError as exc:
        db.rollback()
        logger.warning("POST /api/v1/explanations failed (404): %s", exc)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except FileNotFoundError as exc:
        db.rollback()
        logger.warning("POST /api/v1/explanations failed (404 artifact): %s", exc)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        db.rollback()
        logger.warning("POST /api/v1/explanations failed (400): %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        db.rollback()
        logger.exception(
            "POST /api/v1/explanations failed (unexpected) application_id=%r model_version=%r",
            body.application_id.strip(),
            body.model_version.strip(),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SHAP explanation failed",
        ) from exc


@router.get(
    "/{prediction_id}",
    response_model=ExplanationListResponse,
    summary="저장된 SHAP 설명 조회",
    description=(
        "`prediction_id`(`prediction_result.id`)에 대해 저장된 `explanation_result` 행을 반환합니다. "
        "예측이 없으면 **404**, 예측은 있으나 설명이 아직 없으면 **빈 factors**입니다."
    ),
)
def get_explanation(
    prediction_id: Annotated[
        int,
        Path(description="예측 결과 ID(`prediction_result.id`)"),
    ],
    db: Session = Depends(get_db),
) -> ExplanationListResponse:
    pred = pred_repo.get_prediction_by_id(db, prediction_id)
    if pred is None:
        logger.warning(
            "GET /api/v1/explanations/%s: prediction not found",
            prediction_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"prediction_id={prediction_id} not found",
        )
    rows = expl_repo.list_by_prediction_id(db, prediction_id)
    return _list_response_from_db(
        prediction_id=prediction_id,
        application_id=pred.application_id,
        rows=rows,
    )
