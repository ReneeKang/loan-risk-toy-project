from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


def ping_database(session: Session) -> None:
    """Execute a trivial query to verify the PostgreSQL connection."""
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise RuntimeError("Database ping failed") from exc
