from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories import prediction_repository as pred_repo
from app.schemas.prediction import PredictionCreateRequest, PredictionResponse
from app.services import prediction_service

router = APIRouter(prefix="/api/v1/predictions", tags=["predictions"])


@router.post(
    "",
    response_model=PredictionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="단건 예측 수행",
    description=(
        "**예측을 수행하는 API**입니다. 요청한 `application_id`에 대해 "
        "`loan_application_feature`에서 `model_input_json`을 읽고, "
        "`model_registry`에 등록된 joblib 모델로 `predict_proba` 점수를 계산합니다. "
        "결과(`risk_score`, `predicted_default_yn`, `risk_grade`)는 `prediction_result`에 저장됩니다.\n\n"
        "- 모델·피처 행이 없거나 아티팩트 파일이 없으면 **404**.\n"
        "- 입력 JSON 컬럼이 부족하면 **400**."
    ),
)
def create_prediction(
    body: PredictionCreateRequest,
    db: Session = Depends(get_db),
) -> PredictionResponse:
    try:
        row = prediction_service.run_single_prediction(
            db,
            application_id=body.application_id.strip(),
            model_version=body.model_version.strip(),
        )
        db.commit()
        db.refresh(row)
    except LookupError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except FileNotFoundError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return PredictionResponse.model_validate(row)


@router.get(
    "/{prediction_id}",
    response_model=PredictionResponse,
    summary="예측 결과 조회",
    description=(
        "**저장된 예측 결과를 조회하는 API**입니다. "
        "`prediction_result`의 기본키(`id`)로 단건을 반환합니다. "
        "없으면 **404**입니다."
    ),
)
def get_prediction(
    prediction_id: Annotated[
        int,
        Path(description="조회할 예측 결과 ID(`prediction_result.id`)"),
    ],
    db: Session = Depends(get_db),
) -> PredictionResponse:
    row = pred_repo.get_prediction_by_id(db, prediction_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"prediction_id={prediction_id} not found",
        )
    return PredictionResponse.model_validate(row)
