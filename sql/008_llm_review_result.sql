-- Migration: llm_review_result (LLM-generated 심사 코멘트 per prediction).
-- Idempotent on PostgreSQL.

CREATE TABLE IF NOT EXISTS llm_review_result (
    id               BIGSERIAL PRIMARY KEY,
    application_id   VARCHAR(64) NOT NULL,
    prediction_id    BIGINT NOT NULL REFERENCES prediction_result (id) ON DELETE CASCADE,
    review_comment   TEXT NOT NULL,
    llm_model        VARCHAR(128) NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_llm_review_result_prediction_id UNIQUE (prediction_id)
);

CREATE INDEX IF NOT EXISTS idx_llm_review_result_prediction_id ON llm_review_result (prediction_id);
CREATE INDEX IF NOT EXISTS idx_llm_review_result_application_id ON llm_review_result (application_id);
