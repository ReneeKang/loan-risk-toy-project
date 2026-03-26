from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.health import ping_database
from app.schemas.health import DbHealthResponse, HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/health/db", response_model=DbHealthResponse)
def health_db(db: Session = Depends(get_db)) -> DbHealthResponse:
    ping_database(db)
    return DbHealthResponse(status="ok", database="connected")
