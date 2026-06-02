from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class LlmReviewResponse(BaseModel):
    """심사 코멘트 조회·생성 응답."""

    prediction_id: int = Field(description="예측 결과 PK(`prediction_result.id`)")
    application_id: str = Field(description="신청 ID")
    risk_score: float = Field(description="부실 예측 확률")
    risk_grade: str = Field(description="리스크 등급 A~E")
    predicted_default_yn: str = Field(description="예측 부실 여부 Y/N")
    review_comment: str = Field(description="LLM 생성 심사 코멘트(한국어)")
    llm_model: str = Field(description="사용한 모델명")
    created_at: datetime = Field(description="코멘트 저장 시각(UTC)")

    @field_validator("risk_score", mode="before")
    @classmethod
    def risk_score_float(cls, v: object) -> float:
        return float(v)
