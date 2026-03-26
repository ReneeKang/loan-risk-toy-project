from __future__ import annotations

"""decision_result, decision_rule_hit, risk_policy_rule lookups."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tables import (
    DecisionResult,
    DecisionRuleHit,
    LoanApplicationFeature,
    PredictionResult,
    RiskPolicyRule,
)


def get_prediction_by_id(session: Session, prediction_id: int) -> PredictionResult | None:
    stmt = select(PredictionResult).where(PredictionResult.id == prediction_id)
    return session.execute(stmt).scalar_one_or_none()


def get_feature_by_id(session: Session, feature_id: int) -> LoanApplicationFeature | None:
    stmt = select(LoanApplicationFeature).where(LoanApplicationFeature.id == feature_id)
    return session.execute(stmt).scalar_one_or_none()


def get_decision_by_prediction_id(
    session: Session,
    prediction_id: int,
) -> DecisionResult | None:
    stmt = select(DecisionResult).where(DecisionResult.prediction_id == prediction_id)
    return session.execute(stmt).scalar_one_or_none()


def get_decision_by_id(session: Session, decision_id: int) -> DecisionResult | None:
    stmt = select(DecisionResult).where(DecisionResult.id == decision_id)
    return session.execute(stmt).scalar_one_or_none()


def get_rule_ids_by_codes(session: Session, rule_codes: tuple[str, ...]) -> dict[str, int]:
    stmt = select(RiskPolicyRule).where(RiskPolicyRule.rule_code.in_(rule_codes))
    rows = list(session.execute(stmt).scalars().all())
    return {r.rule_code: int(r.id) for r in rows}


def get_rule_hits_for_decision(
    session: Session,
    decision_id: int,
) -> list[tuple[DecisionRuleHit, RiskPolicyRule]]:
    stmt = (
        select(DecisionRuleHit, RiskPolicyRule)
        .join(RiskPolicyRule, DecisionRuleHit.rule_id == RiskPolicyRule.id)
        .where(DecisionRuleHit.decision_id == decision_id)
        .order_by(DecisionRuleHit.id)
    )
    return list(session.execute(stmt).all())
