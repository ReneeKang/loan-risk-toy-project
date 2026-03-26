from __future__ import annotations

"""
Online prediction: loads artifact from model_registry; input from model_input_json.
Persists prediction_result (risk_score, predicted_default_yn, risk_grade).
"""

from decimal import Decimal
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sqlalchemy.orm import Session

from app.models.tables import ModelRegistry, PredictionResult
from app.repositories import prediction_repository as pred_repo
from app.services.model_service import (
    MODEL_NAME,
    TRAINING_FEATURE_COLUMNS,
    yn_flag_to_binary,
)

DEFAULT_MODEL_VERSION = "LGBM_V1"
DEFAULT_THRESHOLD = 0.5


def risk_grade_from_score(score: float) -> str:
    if score < 0.20:
        return "A"
    if score < 0.40:
        return "B"
    if score < 0.60:
        return "C"
    if score < 0.80:
        return "D"
    return "E"


def predicted_default_yn_from_score(score: float, *, threshold: float = DEFAULT_THRESHOLD) -> str:
    return "Y" if score >= threshold else "N"


def preprocess_prediction_features(df: pd.DataFrame) -> pd.DataFrame:
    """Single row (or batch) with same columns as training; Y/N flags → 0/1 for model matrix."""
    missing = [c for c in TRAINING_FEATURE_COLUMNS if c not in df.columns]
    if missing:
        msg = f"model_input_json missing columns: {missing}"
        raise ValueError(msg)

    out = pd.DataFrame(index=df.index)
    out["annual_income"] = pd.to_numeric(df["annual_income"], errors="coerce")
    out["loan_amount"] = pd.to_numeric(df["loan_amount"], errors="coerce")
    out["interest_rate"] = pd.to_numeric(df["interest_rate"], errors="coerce")
    out["dti"] = pd.to_numeric(df["dti"], errors="coerce")
    out["delinq_2yrs"] = pd.to_numeric(df["delinq_2yrs"], errors="coerce")
    out["loan_amount_to_income_ratio"] = pd.to_numeric(
        df["loan_amount_to_income_ratio"],
        errors="coerce",
    )
    out["high_dti_flag"] = yn_flag_to_binary(df["high_dti_flag"])
    out["prior_delinquency_flag"] = yn_flag_to_binary(df["prior_delinquency_flag"])
    out["risk_grade_encoded"] = pd.to_numeric(df["risk_grade_encoded"], errors="coerce")

    for col in out.columns:
        if col in ("high_dti_flag", "prior_delinquency_flag"):
            continue
        med = out[col].median()
        if pd.isna(med):
            out[col] = out[col].fillna(0.0)
        else:
            out[col] = out[col].fillna(med)

    return out[list(TRAINING_FEATURE_COLUMNS)]


def load_model_from_registry(registry: ModelRegistry) -> LGBMClassifier:
    if not registry.artifact_uri:
        msg = "model_registry.artifact_uri is empty"
        raise ValueError(msg)
    path = Path(registry.artifact_uri)
    if not path.is_file():
        msg = f"Model artifact not found: {path}"
        raise FileNotFoundError(msg)
    return joblib.load(path)


def model_input_json_to_dataframe(model_input_json: dict[str, Any]) -> pd.DataFrame:
    payload = dict(model_input_json) if isinstance(model_input_json, dict) else model_input_json
    return pd.DataFrame([payload])


def run_single_prediction(
    session: Session,
    *,
    application_id: str,
    model_version: str = DEFAULT_MODEL_VERSION,
) -> PredictionResult:
    registry = pred_repo.get_model_registry_by_name_version(
        session,
        model_name=MODEL_NAME,
        model_version=model_version,
    )
    if registry is None:
        msg = f"No model_registry row for model_name={MODEL_NAME!r}, model_version={model_version!r}"
        raise LookupError(msg)
    if not registry.artifact_uri:
        msg = "model_registry.artifact_uri is missing"
        raise LookupError(msg)

    feature_row = pred_repo.get_feature_by_application_and_version(
        session,
        application_id=application_id,
        feature_version=registry.feature_version,
    )
    if feature_row is None:
        msg = (
            f"No loan_application_feature for application_id={application_id!r}, "
            f"feature_version={registry.feature_version!r}"
        )
        raise LookupError(msg)

    mij = feature_row.model_input_json
    if not isinstance(mij, dict):
        msg = "model_input_json must be a JSON object"
        raise ValueError(msg)

    df_raw = model_input_json_to_dataframe(mij)
    X = preprocess_prediction_features(df_raw)

    clf = load_model_from_registry(registry)
    proba = clf.predict_proba(X)[:, 1]
    risk_score = float(np.asarray(proba).reshape(-1)[0])
    risk_score = max(0.0, min(1.0, risk_score))

    grade = risk_grade_from_score(risk_score)
    default_yn = predicted_default_yn_from_score(risk_score)

    row = PredictionResult(
        application_id=application_id,
        feature_id=int(feature_row.id),
        model_registry_id=int(registry.id),
        risk_score=Decimal(str(round(risk_score, 8))),
        risk_grade=grade,
        predicted_default_yn=default_yn,
    )
    session.add(row)
    session.flush()
    return row
