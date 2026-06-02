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

    Set ``LOG_LEVEL=DEBUG`` in ``.env`` for verbose ``app.*`` (router/service) logs.

    Uvicorn may configure the root logger before this runs; in that case
    ``basicConfig`` is skipped and we attach a dedicated handler to the
    ``app`` logger so router/service logs still appear on the console.
    """
    fmt = logging.Formatter(_DEFAULT_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")
    root = logging.getLogger()

    if not root.handlers:
        logging.basicConfig(
            level=level,
            format=_DEFAULT_FORMAT,
            datefmt="%Y-%m-%d %H:%M:%S",
            stream=sys.stderr,
            force=False,
        )
    else:
        root.setLevel(level)

    app_log = logging.getLogger("app")
    app_log.setLevel(level)
    if not app_log.handlers:
        h = logging.StreamHandler(sys.stderr)
        h.setLevel(logging.DEBUG)
        h.setFormatter(fmt)
        app_log.addHandler(h)
        app_log.propagate = False

    # Align common third-party loggers with app level (avoid silent SQLAlchemy/uvicorn noise).
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).setLevel(level)

    # 서버/워커 오류 스트림: ERROR는 최소 INFO 이상에서도 보이도록
    logging.getLogger("uvicorn.error").setLevel(min(level, logging.INFO))

    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
