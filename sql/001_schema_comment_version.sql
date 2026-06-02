-- =============================================================================
-- PostgreSQL COMMENT ON (metadata for \d+ in psql / pg_catalog).
--
-- Apply AFTER:
--   psql ... -f sql/001_schema.sql
--
-- Safe to re-run: COMMENT replaces previous text.
-- Does NOT change table structure or constraints.
-- =============================================================================

COMMENT ON TABLE loan_application_raw IS 'Source-only ingestion: one row per ingested CSV line; uniqueness by source_system + file + line number.';
COMMENT ON COLUMN loan_application_raw.raw_id IS 'Surrogate primary key.';
COMMENT ON COLUMN loan_application_raw.application_id IS 'Optional lender/application id from source payload (not unique on this table).';
COMMENT ON COLUMN loan_application_raw.source_system IS 'Data source identifier (e.g. lending_club).';
COMMENT ON COLUMN loan_application_raw.source_file_name IS 'Original file name for deduplication.';
COMMENT ON COLUMN loan_application_raw.source_row_no IS '1-based row index within that file.';
COMMENT ON COLUMN loan_application_raw.raw_payload IS 'Full source row stored as JSONB.';
COMMENT ON COLUMN loan_application_raw.ingested_at IS 'Insert timestamp (UTC).';

COMMENT ON TABLE loan_application_clean IS 'Normalized loan application; PK is application_id; label target_default_yn is Y or N.';
COMMENT ON COLUMN loan_application_clean.target_default_yn IS 'Historical/training label: Y/N only (binary 0/1 is derived in ML code, not stored here).';
COMMENT ON COLUMN loan_application_clean.raw_id IS 'FK to originating raw row if known.';

COMMENT ON TABLE loan_application_feature IS 'Feature store row per application_id and feature_version; model_input_json is the official model input.';
COMMENT ON COLUMN loan_application_feature.model_input_json IS 'Canonical feature dict for training and online inference.';
COMMENT ON COLUMN loan_application_feature.features IS 'Optional duplicate or extended JSON snapshot; prefer model_input_json for ML.';

COMMENT ON TABLE model_registry IS 'Registered trained models: path, metrics, and linked feature_version.';
COMMENT ON COLUMN model_registry.artifact_uri IS 'Filesystem path to serialized model (e.g. joblib).';
COMMENT ON COLUMN model_registry.is_active IS 'Operational flag; training pipeline may deactivate older rows.';

COMMENT ON TABLE prediction_result IS 'One model prediction: score, grade, and thresholded default flag.';
COMMENT ON COLUMN prediction_result.risk_score IS 'Predicted probability of positive class (default), range [0,1].';
COMMENT ON COLUMN prediction_result.risk_grade IS 'Letter grade A–E derived from score bands.';
COMMENT ON COLUMN prediction_result.predicted_default_yn IS 'Y/N from score threshold (e.g. 0.5), not the same as clean target_default_yn.';

COMMENT ON TABLE risk_policy_rule IS 'Policy rule master; POLICY_* codes are seeded via 006_seed_policy_rules.sql.';
COMMENT ON COLUMN risk_policy_rule.rule_code IS 'Stable code used by application (e.g. POLICY_HIGH_DTI).';
COMMENT ON COLUMN risk_policy_rule.priority IS 'Lower number may be evaluated first in future engines; current engine uses fixed logic.';

COMMENT ON TABLE decision_result IS 'Policy engine outcome per prediction_id; at most one row per prediction (unique).';
COMMENT ON COLUMN decision_result.score_based_decision IS 'Decision from risk_score bands only (APPROVE/REVIEW/DECLINE).';
COMMENT ON COLUMN decision_result.final_decision IS 'After applying risk_policy_rule constraints to score_based_decision.';
COMMENT ON COLUMN decision_result.policy_adjusted_yn IS 'Y if final_decision differs from score_based_decision.';
COMMENT ON COLUMN decision_result.decided_by IS 'system for automated runs; future human reviewer id or name for overrides.';

COMMENT ON TABLE decision_rule_hit IS 'Audit: which risk_policy_rule rows matched when building final_decision.';
COMMENT ON COLUMN decision_rule_hit.detail IS 'JSON snapshot of inputs used when the rule matched.';
