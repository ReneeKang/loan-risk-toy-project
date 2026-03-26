from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(description="전체 상태", examples=["ok"])


class DbHealthResponse(BaseModel):
    status: str = Field(description="전체 상태", examples=["ok"])
    database: str = Field(
        description="DB 연결 상태(연결됨 여부)",
        examples=["connected"],
    )
