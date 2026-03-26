from __future__ import annotations

"""DB access for model_registry, loan_application_feature, prediction_result."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tables import LoanApplicationFeature, ModelRegistry, PredictionResult


def get_model_registry_by_name_version(
    session: Session,
    *,
    model_name: str,
    model_version: str,
) -> ModelRegistry | None:
    stmt = select(ModelRegistry).where(
        ModelRegistry.model_name == model_name,
        ModelRegistry.model_version == model_version,
    )
    return session.execute(stmt).scalar_one_or_none()


def get_feature_by_application_and_version(
    session: Session,
    *,
    application_id: str,
    feature_version: str,
) -> LoanApplicationFeature | None:
    stmt = select(LoanApplicationFeature).where(
        LoanApplicationFeature.application_id == application_id,
        LoanApplicationFeature.feature_version == feature_version,
    )
    return session.execute(stmt).scalar_one_or_none()


def get_prediction_by_id(
    session: Session,
    prediction_id: int,
) -> PredictionResult | None:
    stmt = select(PredictionResult).where(PredictionResult.id == prediction_id)
    return session.execute(stmt).scalar_one_or_none()
