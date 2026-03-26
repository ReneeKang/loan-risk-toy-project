from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load Lending Club CSV into loan_application_raw and loan_application_clean.",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=ROOT / "data" / "raw" / "lending_club.csv",
        help="Path to lending_club.csv",
    )
    parser.add_argument(
        "--mode",
        choices=["sample", "chunk"],
        default="sample",
        help="sample: read first nrows only; chunk: stream in chunksize rows",
    )
    parser.add_argument(
        "--nrows",
        type=int,
        default=1000,
        help="Row limit when mode=sample (default 1000)",
    )
    parser.add_argument(
        "--chunksize",
        type=int,
        default=10000,
        help="Chunk size when mode=chunk (default 10000)",
    )
    args = parser.parse_args()

    from app.core.database import SessionLocal
    from app.services.ingestion_service import run_ingestion

    if not args.csv.is_file():
        logger.error("CSV not found: %s", args.csv)
        raise SystemExit(1)

    session = SessionLocal()
    try:
        total_raw, total_clean = run_ingestion(
            session,
            args.csv,
            args.mode,
            nrows=args.nrows,
            chunksize=args.chunksize,
            source_system="lending_club",
        )
        logger.info(
            "Finished. Inserted raw rows=%s, clean rows=%s",
            total_raw,
            total_clean,
        )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
