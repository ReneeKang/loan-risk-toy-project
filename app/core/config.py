from __future__ import annotations

import logging
import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


def _parse_log_level(name: str | None) -> int:
    if not name or not name.strip():
        return logging.INFO
    return getattr(logging, name.strip().upper(), logging.INFO)


class Settings(BaseModel):
    """Application settings loaded from environment (.env)."""

    database_url: str = Field(
        default="postgresql+psycopg2://postgres:postgres@localhost:5432/loan_risk",
        description="SQLAlchemy URL for PostgreSQL (database: loan_risk)",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL",
    )

    model_config = {"frozen": True}

    def log_level_int(self) -> int:
        """Numeric logging level for ``logging`` module."""
        return _parse_log_level(self.log_level)

    @classmethod
    def from_env(cls) -> Settings:
        url = os.getenv("DATABASE_URL")
        if url is None or url.strip() == "":
            base = cls()
        else:
            if url.startswith("postgresql://") and not url.startswith(
                "postgresql+psycopg2://",
            ):
                url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
            base = cls(database_url=url)
        log_level = os.getenv("LOG_LEVEL", base.log_level)
        return base.model_copy(update={"log_level": log_level})


@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()
