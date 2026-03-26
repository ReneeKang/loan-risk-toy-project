-- Add model_input_json to existing loan_application_feature (pre-refactor DBs).

ALTER TABLE loan_application_feature
    ADD COLUMN IF NOT EXISTS model_input_json JSONB;

UPDATE loan_application_feature
SET model_input_json = features
WHERE model_input_json IS NULL;

ALTER TABLE loan_application_feature
    ALTER COLUMN model_input_json SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_loan_application_feature_model_input_gin
    ON loan_application_feature USING GIN (model_input_json);
