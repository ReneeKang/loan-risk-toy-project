from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


class Settings(BaseModel):
    """Application settings loaded from environment (.env)."""

    database_url: str = Field(
        default="postgresql+psycopg2://postgres:postgres@localhost:5432/loan_risk",
        description="SQLAlchemy URL for PostgreSQL (database: loan_risk)",
    )

    model_config = {"frozen": True}

    @classmethod
    def from_env(cls) -> Settings:
        url = os.getenv("DATABASE_URL")
        if url is None or url.strip() == "":
            return cls()
        if url.startswith("postgresql://") and not url.startswith(
            "postgresql+psycopg2://",
        ):
            url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
        return cls(database_url=url)


@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()
