from __future__ import annotations

"""loan_application_raw and loan_application_clean persistence."""

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tables import LoanApplicationClean, LoanApplicationRaw


def get_existing_source_row_nos(
    session: Session,
    source_system: str,
    source_file_name: str,
    source_row_nos: Iterable[int],
) -> set[int]:
    """Return source_row_no values already stored for this file (idempotent re-runs)."""
    nos = list({int(x) for x in source_row_nos})
    if not nos:
        return set()
    stmt = select(LoanApplicationRaw.source_row_no).where(
        LoanApplicationRaw.source_system == source_system,
        LoanApplicationRaw.source_file_name == source_file_name,
        LoanApplicationRaw.source_row_no.in_(nos),
    )
    return {int(r) for r in session.scalars(stmt).all()}


def get_raw_id_map_by_source_rows(
    session: Session,
    source_system: str,
    source_file_name: str,
    source_row_nos: Iterable[int],
) -> dict[int, int]:
    """Map source_row_no -> raw_id for the given file slice."""
    nos = list({int(x) for x in source_row_nos})
    if not nos:
        return {}
    stmt = select(LoanApplicationRaw.source_row_no, LoanApplicationRaw.raw_id).where(
        LoanApplicationRaw.source_system == source_system,
        LoanApplicationRaw.source_file_name == source_file_name,
        LoanApplicationRaw.source_row_no.in_(nos),
    )
    return {int(sr): int(rid) for sr, rid in session.execute(stmt).all()}


def get_existing_clean_application_ids(
    session: Session,
    application_ids: Iterable[str],
) -> set[str]:
    ids = list({str(x) for x in application_ids if x})
    if not ids:
        return set()
    stmt = select(LoanApplicationClean.application_id).where(
        LoanApplicationClean.application_id.in_(ids),
    )
    return {str(r) for r in session.scalars(stmt).all()}


def insert_raw_batch(session: Session, rows: list[LoanApplicationRaw]) -> int:
    if not rows:
        return 0
    session.add_all(rows)
    session.flush()
    return len(rows)


def insert_clean_batch(session: Session, rows: list[LoanApplicationClean]) -> int:
    if not rows:
        return 0
    session.add_all(rows)
    session.flush()
    return len(rows)
