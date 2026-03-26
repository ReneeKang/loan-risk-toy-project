from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(examples=["ok"])


class DbHealthResponse(BaseModel):
    status: str = Field(examples=["ok"])
    database: str = Field(
        description="Database connectivity",
        examples=["connected"],
    )
