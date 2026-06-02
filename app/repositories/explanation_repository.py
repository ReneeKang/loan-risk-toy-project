from __future__ import annotations

"""DB access for explanation_result (SHAP rows per prediction)."""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.tables import ExplanationResult


def delete_by_prediction_id(session: Session, prediction_id: int) -> None:
    session.execute(
        delete(ExplanationResult).where(ExplanationResult.prediction_id == prediction_id)
    )


def list_by_prediction_id(
    session: Session,
    prediction_id: int,
) -> list[ExplanationResult]:
    stmt = (
        select(ExplanationResult)
        .where(ExplanationResult.prediction_id == prediction_id)
        .order_by(ExplanationResult.rank.asc())
    )
    return list(session.execute(stmt).scalars().all())
