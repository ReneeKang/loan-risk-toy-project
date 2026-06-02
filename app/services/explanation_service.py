from __future__ import annotations

"""
SHAP explanations for LightGBM: load model_input_json + artifact, TreeExplainer,
persist top-K |SHAP| features for the positive (default) class.
"""

from decimal import Decimal
from typing import Any, Literal

import numpy as np
import pandas as pd
import shap
from sqlalchemy.orm import Session

from app.models.tables import ExplanationResult, PredictionResult
from app.repositories import explanation_repository as expl_repo
from app.repositories import prediction_repository as pred_repo
from app.services.model_service import MODEL_NAME
from app.services.prediction_service import (
    load_model_from_registry,
    model_input_json_to_dataframe,
    preprocess_prediction_features,
)

# 상위 영향 변수 개수 (요구: 3~5)
SHAP_TOP_K_MIN = 3
SHAP_TOP_K_MAX = 5


def _shap_values_positive_class(clf: Any, X: pd.DataFrame) -> np.ndarray:
    """Single-row matrix X; returns shape (n_features,) for positive class."""
    explainer = shap.TreeExplainer(clf)
    sv = explainer.shap_values(X)
    if isinstance(sv, list):
        pos = np.asarray(sv[1], dtype=np.float64)
    else:
        pos = np.asarray(sv, dtype=np.float64)
    if pos.ndim == 1:
        return pos
    if pos.ndim == 2 and pos.shape[0] == 1:
        return pos[0]
    msg = f"Unexpected SHAP shape: {getattr(pos, 'shape', None)}"
    raise ValueError(msg)


def _direction_from_shap(val: float) -> Literal["positive", "negative", "neutral"]:
    if val > 0:
        return "positive"
    if val < 0:
        return "negative"
    return "neutral"


def compute_top_shap_features(
    clf: Any,
    X: pd.DataFrame,
) -> list[tuple[str, float, Literal["positive", "negative", "neutral"], float]]:
    """
    Returns list of (feature_name, shap_value, direction, magnitude) sorted by magnitude desc.
    Length between SHAP_TOP_K_MIN and SHAP_TOP_K_MAX (capped by available features).
    """
    if len(X) != 1:
        msg = "SHAP explanation expects a single-row feature matrix"
        raise ValueError(msg)

    raw = _shap_values_positive_class(clf, X)
    names = list(X.columns)
    if len(names) != len(raw):
        msg = f"SHAP length {len(raw)} != columns {len(names)}"
        raise ValueError(msg)

    pairs = [(names[i], float(raw[i])) for i in range(len(names))]
    pairs.sort(key=lambda t: abs(t[1]), reverse=True)

    k = min(SHAP_TOP_K_MAX, len(pairs))
    k = max(min(k, SHAP_TOP_K_MAX), min(SHAP_TOP_K_MIN, len(pairs)))
    top = pairs[:k]

    out: list[tuple[str, float, Literal["positive", "negative", "neutral"], float]] = []
    for name, shap_v in top:
        out.append(
            (
                name,
                shap_v,
                _direction_from_shap(shap_v),
                abs(shap_v),
            )
        )
    return out


def run_explanation_and_persist(
    session: Session,
    *,
    application_id: str,
    model_version: str,
) -> tuple[PredictionResult, list[ExplanationResult]]:
    """
    Resolve latest prediction_result for application + model_version, compute SHAP,
    replace explanation_result rows for that prediction_id.
    """
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

    pred = pred_repo.get_latest_prediction_for_application_and_registry(
        session,
        application_id=application_id,
        model_registry_id=int(registry.id),
    )
    if pred is None:
        msg = (
            f"No prediction_result for application_id={application_id!r} and "
            f"model_version={model_version!r}; run POST /api/v1/predictions first."
        )
        raise LookupError(msg)

    feature_row = pred.feature_row
    if feature_row is None:
        msg = f"loan_application_feature not found for feature_id={pred.feature_id}"
        raise LookupError(msg)

    mij = feature_row.model_input_json
    if not isinstance(mij, dict):
        msg = "model_input_json must be a JSON object"
        raise ValueError(msg)

    df_raw = model_input_json_to_dataframe(mij)
    X = preprocess_prediction_features(df_raw)

    clf = load_model_from_registry(registry)
    top = compute_top_shap_features(clf, X)

    expl_repo.delete_by_prediction_id(session, int(pred.id))

    rows: list[ExplanationResult] = []
    for rank, (fname, shap_v, _dir, _mag) in enumerate(top, start=1):
        rows.append(
            ExplanationResult(
                application_id=pred.application_id,
                prediction_id=int(pred.id),
                feature_name=fname,
                shap_value=Decimal(str(round(shap_v, 8))),
                rank=rank,
            )
        )
    for r in rows:
        session.add(r)
    session.flush()
    return pred, rows


def factor_item_from_row(
    row: ExplanationResult,
) -> dict[str, Any]:
    """API payload fragment for one SHAP row."""
    sv = float(row.shap_value)
    return {
        "feature_name": row.feature_name,
        "shap_value": round(sv, 8),
        "rank": row.rank,
        "direction": _direction_from_shap(sv),
        "magnitude": round(abs(sv), 8),
    }
