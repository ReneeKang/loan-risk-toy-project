from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tables import LoanApplicationClean, LoanApplicationFeature


def fetch_all_cleans(session: Session) -> list[LoanApplicationClean]:
    stmt = select(LoanApplicationClean).order_by(LoanApplicationClean.application_id)
    return list(session.scalars(stmt).all())


def get_existing_feature_application_ids(
    session: Session,
    feature_version: str,
) -> set[str]:
    stmt = select(LoanApplicationFeature.application_id).where(
        LoanApplicationFeature.feature_version == feature_version,
    )
    return {str(r) for r in session.scalars(stmt).all()}


def insert_feature_batch(session: Session, rows: list[LoanApplicationFeature]) -> int:
    if not rows:
        return 0
    session.add_all(rows)
    session.flush()
    return len(rows)
