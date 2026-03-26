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
        description="Train LightGBM binary classifier from loan_application_feature + clean.",
    )
    parser.add_argument(
        "--feature-version",
        default="FTR_V1",
        help="Feature version to read from loan_application_feature (default: FTR_V1)",
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help="Override directory for model joblib (default: ml/artifacts)",
    )
    args = parser.parse_args()

    from app.core.database import SessionLocal
    from app.services.model_service import run_training_pipeline

    session = SessionLocal()
    try:
        path, metrics = run_training_pipeline(
            session,
            artifact_dir=args.artifact_dir,
            feature_version=args.feature_version,
        )
        logger.info("Saved model to %s", path)
        logger.info(
            "Test metrics — roc_auc=%.6f precision=%.6f recall=%.6f f1=%.6f "
            "(train_n=%s test_n=%s)",
            metrics.roc_auc,
            metrics.precision,
            metrics.recall,
            metrics.f1,
            metrics.n_train,
            metrics.n_test,
        )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
