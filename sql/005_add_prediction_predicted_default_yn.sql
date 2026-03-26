-- Migration: add prediction_result.predicted_default_yn (pre-001 DBs only).
-- Canonical: sql/001_schema.sql. Skip if column already exists. Policy: sql/README.md

ALTER TABLE prediction_result
    ADD COLUMN IF NOT EXISTS predicted_default_yn CHAR(1);

UPDATE prediction_result
SET predicted_default_yn = 'N'
WHERE predicted_default_yn IS NULL;

ALTER TABLE prediction_result
    ALTER COLUMN predicted_default_yn SET NOT NULL;

ALTER TABLE prediction_result
    DROP CONSTRAINT IF EXISTS chk_prediction_predicted_default_yn;

ALTER TABLE prediction_result
    ADD CONSTRAINT chk_prediction_predicted_default_yn
    CHECK (predicted_default_yn IN ('Y', 'N'));
