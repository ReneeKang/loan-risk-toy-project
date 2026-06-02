from __future__ import annotations

"""DB access for llm_review_result."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tables import LlmReviewResult


def get_by_prediction_id(
    session: Session,
    prediction_id: int,
) -> LlmReviewResult | None:
    stmt = select(LlmReviewResult).where(LlmReviewResult.prediction_id == prediction_id)
    return session.execute(stmt).scalar_one_or_none()
