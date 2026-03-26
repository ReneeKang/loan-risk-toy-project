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
        description="Build loan_application_feature rows from loan_application_clean.",
    )
    parser.add_argument(
        "--feature-version",
        default="FTR_V1",
        help="Feature version string (default: FTR_V1)",
    )
    args = parser.parse_args()

    from app.core.database import SessionLocal
    from app.services.feature_service import run_feature_build

    session = SessionLocal()
    try:
        inserted, skipped = run_feature_build(
            session,
            feature_version=args.feature_version,
        )
        logger.info(
            "Done. inserted=%s skipped=%s (already present or batch complete)",
            inserted,
            skipped,
        )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
