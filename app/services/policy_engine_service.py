from __future__ import annotations

"""
Policy engine: risk_score bands + model_input_json flags -> final decision.
Persists decision_result and decision_rule_hit (requires sql/006_seed_policy_rules.sql).
"""

from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models.tables import DecisionResult, DecisionRuleHit
from app.repositories import decision_repository as dec_repo
from app.schemas.decision import DecisionResponse, RuleHitItem

RULE_CODES: tuple[str, ...] = (
    "POLICY_HIGH_DTI",
    "POLICY_PRIOR_DELINQ",
    "POLICY_HIGH_LTI",
)

_DECISION_RANK: dict[str, int] = {"APPROVE": 0, "REVIEW": 1, "DECLINE": 2}


def _max_decision(*decisions: str) -> str:
    return max(decisions, key=lambda d: _DECISION_RANK[d])


def score_to_band(score: float) -> str:
    if score < 0.4:
        return "APPROVE"
    if score < 0.7:
        return "REVIEW"
    return "DECLINE"


def yn_normalize(value: Any) -> str:
    if value is None:
        return "N"
    s = str(value).strip().upper()
    if s in ("Y", "1", "TRUE", "YES"):
        return "Y"
    return "N"


def loan_ratio(mij: dict[str, Any]) -> float | None:
    v = mij.get("loan_amount_to_income_ratio")
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def evaluate_policy(
    risk_score: float,
    mij: dict[str, Any],
) -> tuple[
    str,
    str,
    str,
    str,
    list[tuple[str, dict[str, Any]]],
]:
    """
    Returns (score_based, final, policy_adjusted_yn, summary, fired rules as (code, detail)).
    """
    score_based = score_to_band(risk_score)
    high_dti = yn_normalize(mij.get("high_dti_flag"))
    prior = yn_normalize(mij.get("prior_delinquency_flag"))
    ratio = loan_ratio(mij)

    candidates: list[str] = [score_based]
    fired: list[tuple[str, dict[str, Any]]] = []

    if prior == "Y":
        candidates.append("DECLINE")
        fired.append(("POLICY_PRIOR_DELINQ", {"prior_delinquency_flag": "Y"}))
    if high_dti == "Y":
        candidates.append("REVIEW")
        fired.append(("POLICY_HIGH_DTI", {"high_dti_flag": "Y"}))
    if ratio is not None and ratio >= 0.7:
        candidates.append("REVIEW")
        fired.append(("POLICY_HIGH_LTI", {"loan_amount_to_income_ratio": ratio}))

    final = _max_decision(*candidates)
    policy_adj = "Y" if final != score_based else "N"

    parts: list[str] = [f"score_tier={score_based}"]
    if policy_adj == "Y":
        parts.append(f"after_policy={final}")
        parts.append("; ".join(code for code, _ in fired) if fired else "policy_adjust")
    summary = " | ".join(parts)

    return score_based, final, policy_adj, summary, fired


def run_policy_decision(session: Session, prediction_id: int) -> tuple[DecisionResult, bool]:
    """
    Create decision for prediction_id, or return existing if already present.

    Returns (decision, is_new). is_new False means duplicate (no insert).

    Raises:
        LookupError: prediction not found
        ValueError: feature or model_input_json invalid
        RuntimeError: policy rules not seeded in DB
    """
    existing = dec_repo.get_decision_by_prediction_id(session, prediction_id)
    if existing is not None:
        return existing, False

    pred = dec_repo.get_prediction_by_id(session, prediction_id)
    if pred is None:
        raise LookupError(f"prediction_id={prediction_id} not found")

    feat = dec_repo.get_feature_by_id(session, int(pred.feature_id))
    if feat is None:
        raise ValueError(f"loan_application_feature not found for feature_id={pred.feature_id}")

    mij = feat.model_input_json
    if not isinstance(mij, dict):
        raise ValueError("model_input_json must be a JSON object")

    score = float(pred.risk_score) if isinstance(pred.risk_score, Decimal) else float(pred.risk_score)

    score_based, final, policy_adj, summary, fired = evaluate_policy(score, mij)

    rule_map = dec_repo.get_rule_ids_by_codes(session, RULE_CODES)
    missing = [c for c in RULE_CODES if c not in rule_map]
    if missing:
        msg = f"Missing risk_policy_rule rows for codes {missing}. Run sql/006_seed_policy_rules.sql"
        raise RuntimeError(msg)

    row = DecisionResult(
        application_id=pred.application_id,
        prediction_id=prediction_id,
        system_decision=score_based,
        score_based_decision=score_based,
        final_decision=final,
        policy_adjusted_yn=policy_adj,
        decision_reason_summary=summary,
        override_yn="N",
        decided_by="system",
        override_flag=False,
    )
    session.add(row)
    session.flush()

    for code, detail in fired:
        rid = rule_map[code]
        session.add(
            DecisionRuleHit(
                decision_id=int(row.id),
                rule_id=rid,
                matched=True,
                detail=detail,
            ),
        )
    session.flush()

    return row, True


def decision_to_response(session: Session, decision: DecisionResult) -> DecisionResponse:
    """Load rule hits and build API response."""
    hits = dec_repo.get_rule_hits_for_decision(session, int(decision.id))
    items: list[RuleHitItem] = []
    for hit, rule in hits:
        items.append(
            RuleHitItem(
                rule_code=rule.rule_code,
                rule_name=rule.rule_name,
                matched=hit.matched,
                detail=hit.detail,
            ),
        )
    return DecisionResponse(
        id=int(decision.id),
        application_id=decision.application_id,
        prediction_id=int(decision.prediction_id),
        system_decision=decision.system_decision,
        score_based_decision=decision.score_based_decision,
        final_decision=decision.final_decision,
        policy_adjusted_yn=decision.policy_adjusted_yn,
        decision_reason_summary=decision.decision_reason_summary,
        override_yn=decision.override_yn,
        decided_by=decision.decided_by,
        decided_at=decision.decided_at,
        rule_hits=items,
    )
