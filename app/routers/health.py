from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.health import ping_database
from app.schemas.health import DbHealthResponse, HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="애플리케이션 헬스 체크",
    description=(
        "서버 프로세스가 정상 응답하는지 확인합니다. "
        "데이터베이스 연결 여부는 `/health/db`를 사용하세요."
    ),
)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/health/db",
    response_model=DbHealthResponse,
    summary="데이터베이스 연결 헬스 체크",
    description=(
        "PostgreSQL에 SQL 세션으로 접속해 `SELECT 1`을 실행합니다. "
        "연결 실패 시 500 계열 오류로 응답할 수 있습니다."
    ),
)
def health_db(db: Session = Depends(get_db)) -> DbHealthResponse:
    ping_database(db)
    return DbHealthResponse(status="ok", database="connected")
