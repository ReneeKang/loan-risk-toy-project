from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ExplanationCreateRequest(BaseModel):
    application_id: str = Field(
        ...,
        min_length=1,
        description="대출 신청 ID(`loan_application_clean.application_id`와 동일)",
        examples=["12345"],
    )
    model_version: str = Field(
        default="LGBM_V1",
        description="사용할 모델 버전(`model_registry.model_version`); 해당 버전으로 저장된 예측이 있어야 합니다.",
        examples=["LGBM_V1"],
    )


class ExplanationFactorItem(BaseModel):
    feature_name: str = Field(description="모델 입력 피처명(전처리 후 컬럼)")
    shap_value: float = Field(description="양성(부실) 클래스에 대한 SHAP 기여값")
    rank: int = Field(description="|SHAP| 기준 순위(1이 가장 큼)")
    direction: Literal["positive", "negative", "neutral"] = Field(
        description="부실 확률 증가(+) / 감소(-) / 중립(0) 방향",
    )
    magnitude: float = Field(description="|shap_value|")


class ExplanationListResponse(BaseModel):
    prediction_id: int = Field(description="연결된 `prediction_result.id`")
    application_id: str = Field(description="신청 ID")
    factors: list[ExplanationFactorItem] = Field(
        default_factory=list,
        description="SHAP 상위 요인(저장된 행 순서, 보통 3~5개)",
    )
