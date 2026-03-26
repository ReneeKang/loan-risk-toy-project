from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PredictionCreateRequest(BaseModel):
    application_id: str = Field(
        ...,
        min_length=1,
        description="대출 신청 ID(`loan_application_clean.application_id`와 동일)",
        examples=["12345"],
    )
    model_version: str = Field(
        default="LGBM_V1",
        description="사용할 모델 버전(`model_registry.model_version`, 기본: LGBM_V1)",
        examples=["LGBM_V1"],
    )


class PredictionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="예측 결과 PK(`prediction_result.id`)")
    application_id: str = Field(description="신청 ID")
    feature_id: int = Field(
        description="참조한 피처 행 ID(`loan_application_feature.id`)",
    )
    model_registry_id: int = Field(
        description="사용한 모델 등록 ID(`model_registry.id`)",
    )
    risk_score: float = Field(
        ...,
        description="부실(연체) 양성 클래스 확률(`predict_proba` 두 번째 값, 0~1)",
    )
    risk_grade: str = Field(
        description="점수 구간에 따른 리스크 등급(A~E)",
    )
    predicted_default_yn: str = Field(
        description="임계값(기본 0.5) 기준 이진 예측 라벨(Y/N)",
    )
    predicted_at: datetime = Field(description="예측 시각(UTC)")

    @field_validator("risk_score", mode="before")
    @classmethod
    def risk_score_as_float(cls, v: object) -> float:
        if isinstance(v, Decimal):
            return float(v)
        return float(v)
