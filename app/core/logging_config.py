from __future__ import annotations

import logging
import sys
from typing import Final

_DEFAULT_FORMAT: Final[str] = (
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)


def configure_logging(level: int = logging.INFO) -> None:
    """
    Send application logs to stderr (console). Safe to call once at startup.
    """
    root = logging.getLogger()
    if root.handlers:
        root.setLevel(level)
        return

    logging.basicConfig(
        level=level,
        format=_DEFAULT_FORMAT,
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
        force=False,
    )

    # Align common third-party loggers with app level (avoid silent SQLAlchemy/uvicorn noise).
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).setLevel(level)

    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
