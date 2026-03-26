from __future__ import annotations

"""
Feature build: persists rows in loan_application_feature.

Official model input: model_input_json (must match training/inference column contract).
The `features` column is populated with the same payload for compatibility; new code
should read model_input_json only.
"""

from typing import Any

from sqlalchemy.orm import Session

from app.models.tables import LoanApplicationClean, LoanApplicationFeature
from app.repositories import feature_repository as feat_repo

FEATURE_VERSION = "FTR_V1"


def target_default_yn_to_binary(yn: str) -> int:
    """
    Training-only label mapping (not persisted on clean).
    Y -> 1 (default), N -> 0 (non-default).
    """
    s = str(yn).strip().upper()
    if s == "Y":
        return 1
    if s == "N":
        return 0
    msg = f"Invalid target_default_yn: {yn!r}"
    raise ValueError(msg)


def encode_grade(grade: str | None) -> int | None:
    """Lending Club grade first letter: A=1 .. G=7."""
    if grade is None:
        return None
    g = str(grade).strip().upper()
    if not g:
        return None
    c = g[0]
    if "A" <= c <= "G":
        return ord(c) - ord("A") + 1
    return None


def _to_float(v: Decimal | float | int | None) -> float | None:
    if v is None:
        return None
    return float(v)


def build_model_input_dict(clean: LoanApplicationClean) -> dict[str, Any]:
    """Build model_input_json from a clean row."""
    annual_inc = clean.annual_inc
    loan_amnt = clean.loan_amnt
    int_rate = clean.int_rate
    dti = clean.dti
    delinq = clean.delinq_2yrs if clean.delinq_2yrs is not None else 0

    ratio: float | None = None
    if (
        annual_inc is not None
        and annual_inc > 0
        and loan_amnt is not None
    ):
        ratio = float(loan_amnt) / float(annual_inc)

    dti_val = float(dti) if dti is not None else None
    high_dti = "N"
    if dti_val is not None and dti_val >= 30:
        high_dti = "Y"

    prior_del = "Y" if delinq >= 1 else "N"

    risk_enc = encode_grade(clean.grade)

    return {
        "application_id": clean.application_id,
        "annual_income": _to_float(annual_inc),
        "loan_amount": _to_float(loan_amnt),
        "interest_rate": _to_float(int_rate),
        "dti": dti_val,
        "delinq_2yrs": int(delinq),
        "grade": (clean.grade or "").strip() or None,
        "loan_amount_to_income_ratio": ratio,
        "high_dti_flag": high_dti,
        "prior_delinquency_flag": prior_del,
        "risk_grade_encoded": risk_enc,
    }


def run_feature_build(
    session: Session,
    *,
    feature_version: str = FEATURE_VERSION,
) -> tuple[int, int]:
    """
    Build features from loan_application_clean and insert into loan_application_feature.
    Returns (rows_inserted, rows_skipped).
    """
    cleans = feat_repo.fetch_all_cleans(session)
    if not cleans:
        return 0, 0

    existing = feat_repo.get_existing_feature_application_ids(session, feature_version)
    inserted = 0
    skipped = 0
    batch: list[LoanApplicationFeature] = []

    for clean in cleans:
        if clean.application_id in existing:
            skipped += 1
            continue

        payload = build_model_input_dict(clean)
        row = LoanApplicationFeature(
            application_id=clean.application_id,
            feature_version=feature_version,
            features=payload,
            model_input_json=payload,
        )
        batch.append(row)

        if len(batch) >= 500:
            inserted += feat_repo.insert_feature_batch(session, batch)
            session.commit()
            batch.clear()

    if batch:
        inserted += feat_repo.insert_feature_batch(session, batch)
        session.commit()

    return inserted, skipped
