from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.decision import DecisionConflictBody, DecisionCreateRequest, DecisionResponse
from app.services import policy_engine_service

router = APIRouter(prefix="/api/v1/decisions", tags=["decisions"])


@router.post(
    "",
    response_model=None,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "심사 결정 생성", "model": DecisionResponse},
        409: {
            "description": "동일 prediction_id에 대한 심사 결정이 이미 존재",
            "model": DecisionConflictBody,
        },
        503: {"description": "정책 룰 마스터 미시드(006 시드 필요)"},
    },
    summary="심사 결정(정책 엔진) 생성",
    description=(
        "`prediction_id`에 대해 `prediction_result`의 **risk_score**와 "
        "`loan_application_feature.model_input_json`의 플래그/비율로 "
        "점수 구간 판정 후 정책 룰을 적용해 **final_decision**을 저장합니다. "
        "이미 결정이 있으면 **409**와 기존 본문을 반환합니다."
    ),
)
def create_decision(
    body: DecisionCreateRequest,
    db: Session = Depends(get_db),
):
    try:
        decision, is_new = policy_engine_service.run_policy_decision(
            db,
            body.prediction_id,
        )
    except LookupError as exc:
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
    except RuntimeError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    if not is_new:
        dr = policy_engine_service.decision_to_response(db, decision)
        conflict = DecisionConflictBody(
            detail="이미 해당 예측(prediction_id)에 대한 심사 결정이 존재합니다.",
            decision=dr,
        )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=conflict.model_dump(mode="json"),
        )

    db.commit()
    db.refresh(decision)
    return policy_engine_service.decision_to_response(db, decision)


@router.get(
    "/{decision_id}",
    response_model=DecisionResponse,
    summary="심사 결정 조회",
    description="`decision_result.id`로 저장된 심사 결정과 적용된 정책 룰 히트를 조회합니다.",
)
def get_decision(
    decision_id: Annotated[
        int,
        Path(description="심사 결정 ID(`decision_result.id`)"),
    ],
    db: Session = Depends(get_db),
) -> DecisionResponse:
    from app.repositories import decision_repository as dec_repo

    row = dec_repo.get_decision_by_id(db, decision_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"decision_id={decision_id} not found",
        )
    return policy_engine_service.decision_to_response(db, row)
