from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DecisionCreateRequest(BaseModel):
    prediction_id: int = Field(
        ...,
        description="예측 결과 ID(`prediction_result.id`). 이미 심사 결정이 있으면 409.",
        examples=[1],
    )


class RuleHitItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rule_code: str = Field(description="정책 룰 코드")
    rule_name: str = Field(description="룰 이름")
    matched: bool = Field(description="이번 심사에서 조건 충족 여부")
    detail: dict | None = Field(default=None, description="룰 평가 시점 스냅샷(JSON)")


class DecisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="심사 결정 PK(`decision_result.id`)")
    application_id: str = Field(description="신청 ID")
    prediction_id: int = Field(description="연결된 예측 ID")
    system_decision: str = Field(description="점수 구간만 반영한 결정(현재는 score_based와 동일)")
    score_based_decision: str = Field(description="risk_score 구간만으로 산출(APPROVE/REVIEW/DECLINE)")
    final_decision: str = Field(description="정책 룰 반영 후 최종 결정")
    policy_adjusted_yn: str = Field(description="정책으로 점수구간 결과가 바뀌었으면 Y")
    decision_reason_summary: str | None = Field(description="판정 요약 문자열")
    override_yn: str = Field(description="수동 오버라이드 여부(Y/N), 시스템은 N")
    decided_by: str = Field(description="결정 주체(system 등)")
    decided_at: datetime = Field(description="결정 시각")
    rule_hits: list[RuleHitItem] = Field(default_factory=list, description="충족된 정책 룰 목록")


class DecisionConflictBody(BaseModel):
    detail: str = Field(description="중복 사유")
    decision: DecisionResponse = Field(description="기존 심사 결정")
