from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.models.tables import LoanApplicationClean, LoanApplicationFeature, ModelRegistry

MODEL_NAME = "loan_risk_lgbm"
MODEL_VERSION = "LGBM_V1"
FEATURE_VERSION = "FTR_V1"
ALGORITHM = "lightgbm"

TRAINING_FEATURE_COLUMNS: tuple[str, ...] = (
    "annual_income",
    "loan_amount",
    "interest_rate",
    "dti",
    "delinq_2yrs",
    "loan_amount_to_income_ratio",
    "high_dti_flag",
    "prior_delinquency_flag",
    "risk_grade_encoded",
)


@dataclass(frozen=True)
class TrainingMetrics:
    roc_auc: float
    precision: float
    recall: float
    f1: float
    n_train: int
    n_test: int


def load_joined_training_frame(
    session: Session,
    *,
    feature_version: str = FEATURE_VERSION,
) -> pd.DataFrame:
    """
    Join loan_application_feature and loan_application_clean on application_id,
    expand model_input_json into columns, attach target_default_yn from clean.
    """
    stmt = (
        select(
            LoanApplicationFeature.model_input_json,
            LoanApplicationClean.target_default_yn,
        )
        .join(
            LoanApplicationClean,
            LoanApplicationFeature.application_id == LoanApplicationClean.application_id,
        )
        .where(LoanApplicationFeature.feature_version == feature_version)
    )
    rows = session.execute(stmt).all()
    if not rows:
        msg = "No rows found for training (check feature_version and feature table)."
        raise ValueError(msg)

    records: list[dict[str, Any]] = []
    for mij, tyn in rows:
        payload = dict(mij) if isinstance(mij, dict) else mij
        payload = {**payload, "target_default_yn": tyn}
        records.append(payload)

    return pd.DataFrame.from_records(records)


def target_default_yn_to_int(series: pd.Series) -> pd.Series:
    m = series.astype(str).str.strip().str.upper()
    out = m.map({"Y": 1, "N": 0})
    if out.isna().any():
        msg = "target_default_yn must be Y or N for all rows"
        raise ValueError(msg)
    return out.astype(int)


def yn_flag_to_binary(series: pd.Series) -> pd.Series:
    def _one(v: Any) -> float:
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return 0.0
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return float(int(v))
        s = str(v).strip().upper()
        return 1.0 if s == "Y" else 0.0

    return series.map(_one).astype(float)


def preprocess_training_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Null handling, numeric conversion, Y/N flags -> 0/1 for model matrix."""
    required = (*TRAINING_FEATURE_COLUMNS, "target_default_yn")
    missing = [c for c in required if c not in df.columns]
    if missing:
        msg = f"Missing columns for training: {missing}"
        raise ValueError(msg)

    y = target_default_yn_to_int(df["target_default_yn"])

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
    out["risk_grade_encoded"] = pd.to_numeric(
        df["risk_grade_encoded"],
        errors="coerce",
    )

    for col in out.columns:
        if col in ("high_dti_flag", "prior_delinquency_flag"):
            continue
        med = out[col].median()
        if pd.isna(med):
            out[col] = out[col].fillna(0.0)
        else:
            out[col] = out[col].fillna(med)

    return out[list(TRAINING_FEATURE_COLUMNS)], y


def train_lightgbm_binary(
    X: pd.DataFrame,
    y: pd.Series,
    *,
    test_size: float = 0.2,
    random_state: int = 42,
) -> tuple[LGBMClassifier, TrainingMetrics]:
    if len(X) < 10:
        msg = f"Not enough rows for train/test split: {len(X)}"
        raise ValueError(msg)

    stratify = y if y.nunique() > 1 else None
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=test_size,
        random_state=random_state,
        stratify=stratify,
    )

    clf = LGBMClassifier(
        objective="binary",
        random_state=random_state,
        n_estimators=200,
        learning_rate=0.05,
        num_leaves=31,
        n_jobs=-1,
        verbose=-1,
    )
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    y_proba = clf.predict_proba(X_test)[:, 1]

    metrics = TrainingMetrics(
        roc_auc=float(roc_auc_score(y_test, y_proba)),
        precision=float(precision_score(y_test, y_pred, zero_division=0)),
        recall=float(recall_score(y_test, y_pred, zero_division=0)),
        f1=float(f1_score(y_test, y_pred, zero_division=0)),
        n_train=len(X_train),
        n_test=len(X_test),
    )
    return clf, metrics


def save_model_artifact(model: LGBMClassifier, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)


def register_model_in_registry(
    session: Session,
    metrics: TrainingMetrics,
    artifact_path: str,
) -> None:
    """Persist model metadata; sets this row active and deactivates other loan_risk_lgbm rows."""
    session.execute(
        update(ModelRegistry)
        .where(ModelRegistry.model_name == MODEL_NAME)
        .values(is_active=False),
    )

    session.execute(
        delete(ModelRegistry).where(
            ModelRegistry.model_name == MODEL_NAME,
            ModelRegistry.model_version == MODEL_VERSION,
        ),
    )

    row = ModelRegistry(
        model_name=MODEL_NAME,
        model_version=MODEL_VERSION,
        algorithm=ALGORITHM,
        feature_version=FEATURE_VERSION,
        auc=Decimal(str(round(metrics.roc_auc, 6))),
        precision_=Decimal(str(round(metrics.precision, 6))),
        recall=Decimal(str(round(metrics.recall, 6))),
        artifact_uri=artifact_path,
        is_active=True,
        trained_at=datetime.now(timezone.utc),
    )
    session.add(row)
    session.flush()


def run_training_pipeline(
    session: Session,
    *,
    artifact_dir: Path | None = None,
    feature_version: str = FEATURE_VERSION,
) -> tuple[Path, TrainingMetrics]:
    """
    Load data, train LightGBM, save joblib under ml/artifacts/, register model_registry.
    Returns (artifact_path, metrics).
    """
    raw_df = load_joined_training_frame(session, feature_version=feature_version)
    X, y = preprocess_training_features(raw_df)
    model, metrics = train_lightgbm_binary(X, y)

    base = artifact_dir or Path(__file__).resolve().parents[2] / "ml" / "artifacts"
    artifact_path = base / f"{MODEL_NAME}_{MODEL_VERSION}.joblib"
    save_model_artifact(model, artifact_path)

    register_model_in_registry(session, metrics, str(artifact_path.resolve()))
    session.commit()

    return artifact_path, metrics
