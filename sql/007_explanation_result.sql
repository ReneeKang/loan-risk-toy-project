-- Migration: explanation_result (SHAP top features per prediction).
-- Idempotent on PostgreSQL: skip if table already exists.

CREATE TABLE IF NOT EXISTS explanation_result (
    id               BIGSERIAL PRIMARY KEY,
    application_id   VARCHAR(64) NOT NULL,
    prediction_id    BIGINT NOT NULL REFERENCES prediction_result (id) ON DELETE CASCADE,
    feature_name     VARCHAR(128) NOT NULL,
    shap_value       NUMERIC(14, 8) NOT NULL,
    rank             INTEGER NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_explanation_result_prediction_feature UNIQUE (prediction_id, feature_name),
    CONSTRAINT chk_explanation_rank_positive CHECK (rank >= 1)
);

CREATE INDEX IF NOT EXISTS idx_explanation_result_prediction_id ON explanation_result (prediction_id);
CREATE INDEX IF NOT EXISTS idx_explanation_result_application_id ON explanation_result (application_id);
