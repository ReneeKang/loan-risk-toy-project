-- =============================================================================
-- CANONICAL SCHEMA for database loan_risk (apply after 000_create_database.sql).
--
-- Frozen roles (do not repurpose these tables):
--   raw:              source ingestion; raw_payload + source line identity
--   clean:            normalized application; target_default_yn IN ('Y','N') only
--   feature:          model_input_json = official ML input; feature_version
--   model_registry:   model metadata, artifact_uri, feature_version link
--   prediction_result: official outputs risk_score, predicted_default_yn, risk_grade
--
-- Further changes: ADD COLUMN or new sql/NNN_*.sql migrations only.
-- =============================================================================

-- raw: immutable source rows
CREATE TABLE loan_application_raw (
    raw_id           BIGSERIAL PRIMARY KEY,
    application_id   VARCHAR(64),
    source_system    VARCHAR(64) NOT NULL DEFAULT 'lending_club',
    source_file_name VARCHAR(512) NOT NULL,
    source_row_no    INTEGER NOT NULL,
    raw_payload      JSONB NOT NULL,
    ingested_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_loan_application_raw_source_line UNIQUE (source_system, source_file_name, source_row_no)
);

CREATE INDEX idx_loan_application_raw_application_id ON loan_application_raw (application_id);
CREATE INDEX idx_loan_application_raw_ingested_at ON loan_application_raw (ingested_at);
CREATE INDEX idx_loan_application_raw_source_system ON loan_application_raw (source_system);
CREATE INDEX idx_loan_application_raw_source_file ON loan_application_raw (source_file_name);

-- clean: normalized labels; training label Y/N only on this layer
CREATE TABLE loan_application_clean (
    application_id       VARCHAR(64) NOT NULL PRIMARY KEY,
    raw_id                 BIGINT REFERENCES loan_application_raw (raw_id) ON DELETE SET NULL,
    loan_amnt              NUMERIC(14, 2),
    term                   VARCHAR(32),
    term_months            INTEGER,
    int_rate               NUMERIC(8, 4),
    installment            NUMERIC(14, 2),
    grade                  VARCHAR(8),
    sub_grade              VARCHAR(8),
    emp_title              VARCHAR(256),
    emp_length             VARCHAR(64),
    home_ownership         VARCHAR(32),
    annual_inc             NUMERIC(16, 2),
    verification_status    VARCHAR(32),
    issue_d                DATE,
    loan_status            VARCHAR(64),
    purpose                VARCHAR(128),
    zip_code               VARCHAR(16),
    addr_state             VARCHAR(8),
    dti                    NUMERIC(8, 4),
    delinq_2yrs            INTEGER,
    earliest_cr_line       DATE,
    open_acc               INTEGER,
    pub_rec                INTEGER,
    revol_bal              NUMERIC(16, 2),
    revol_util             NUMERIC(8, 4),
    total_acc              INTEGER,
    target_default_yn      CHAR(1) NOT NULL,
    cleaned_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_target_default_yn CHECK (target_default_yn IN ('Y', 'N'))
);

CREATE INDEX idx_loan_application_clean_raw_id ON loan_application_clean (raw_id);
CREATE INDEX idx_loan_application_clean_loan_status ON loan_application_clean (loan_status);

-- feature: official model input is model_input_json (features may mirror for audit)
CREATE TABLE loan_application_feature (
    id                 BIGSERIAL PRIMARY KEY,
    application_id     VARCHAR(64) NOT NULL REFERENCES loan_application_clean (application_id) ON DELETE CASCADE,
    feature_version    VARCHAR(64) NOT NULL,
    features           JSONB NOT NULL,
    model_input_json   JSONB NOT NULL,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_loan_application_feature_app_version UNIQUE (application_id, feature_version)
);

CREATE INDEX idx_loan_application_feature_application_id ON loan_application_feature (application_id);
CREATE INDEX idx_loan_application_feature_features_gin ON loan_application_feature USING GIN (features);
CREATE INDEX idx_loan_application_feature_model_input_gin ON loan_application_feature USING GIN (model_input_json);

-- model_registry: artifact + version metadata
CREATE TABLE model_registry (
    id               BIGSERIAL PRIMARY KEY,
    model_name       VARCHAR(128) NOT NULL,
    model_version    VARCHAR(64) NOT NULL,
    algorithm        VARCHAR(64) NOT NULL,
    feature_version  VARCHAR(64) NOT NULL,
    auc              NUMERIC(7, 6),
    recall           NUMERIC(7, 6),
    precision        NUMERIC(7, 6),
    artifact_uri     TEXT,
    is_active        BOOLEAN NOT NULL DEFAULT FALSE,
    trained_at       TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_model_registry_name_version UNIQUE (model_name, model_version)
);

CREATE INDEX idx_model_registry_active ON model_registry (is_active) WHERE is_active = TRUE;

-- prediction_result: official scores (risk_score, predicted_default_yn, risk_grade)
CREATE TABLE prediction_result (
    id                     BIGSERIAL PRIMARY KEY,
    application_id         VARCHAR(64) NOT NULL,
    feature_id             BIGINT NOT NULL REFERENCES loan_application_feature (id) ON DELETE RESTRICT,
    model_registry_id      BIGINT NOT NULL REFERENCES model_registry (id) ON DELETE RESTRICT,
    risk_score             NUMERIC(10, 8) NOT NULL,
    risk_grade             CHAR(1) NOT NULL,
    predicted_default_yn   CHAR(1) NOT NULL,
    predicted_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_prediction_risk_score CHECK (risk_score >= 0::NUMERIC AND risk_score <= 1::NUMERIC),
    CONSTRAINT chk_prediction_risk_grade CHECK (risk_grade IN ('A', 'B', 'C', 'D', 'E')),
    CONSTRAINT chk_prediction_predicted_default_yn CHECK (predicted_default_yn IN ('Y', 'N'))
);

CREATE INDEX idx_prediction_result_application_id ON prediction_result (application_id);
CREATE INDEX idx_prediction_result_model_registry_id ON prediction_result (model_registry_id);
CREATE INDEX idx_prediction_result_predicted_at ON prediction_result (predicted_at);

-- decision / policy (extend via new columns or migrations; separate from core ML pipeline roles above)
CREATE TABLE risk_policy_rule (
    id            BIGSERIAL PRIMARY KEY,
    rule_code     VARCHAR(64) NOT NULL UNIQUE,
    rule_name     VARCHAR(256) NOT NULL,
    description   TEXT,
    priority      INTEGER NOT NULL DEFAULT 100,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    condition_sql TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_risk_policy_rule_active_priority ON risk_policy_rule (is_active, priority);

CREATE TABLE decision_result (
    id                      BIGSERIAL PRIMARY KEY,
    application_id        VARCHAR(64) NOT NULL,
    prediction_id         BIGINT NOT NULL REFERENCES prediction_result (id) ON DELETE RESTRICT,
    system_decision       VARCHAR(32) NOT NULL,
    score_based_decision  VARCHAR(32) NOT NULL,
    final_decision        VARCHAR(32) NOT NULL,
    policy_adjusted_yn    CHAR(1) NOT NULL,
    decision_reason_summary TEXT,
    override_yn           CHAR(1) NOT NULL DEFAULT 'N',
    decided_by            VARCHAR(64) NOT NULL DEFAULT 'system',
    override_flag         BOOLEAN NOT NULL DEFAULT FALSE,
    overridden_by         VARCHAR(128),
    override_reason       TEXT,
    decided_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_decision_result_prediction_id UNIQUE (prediction_id),
    CONSTRAINT chk_decision_system CHECK (system_decision IN ('APPROVE', 'REVIEW', 'DECLINE')),
    CONSTRAINT chk_decision_score_based CHECK (score_based_decision IN ('APPROVE', 'REVIEW', 'DECLINE')),
    CONSTRAINT chk_decision_final CHECK (final_decision IN ('APPROVE', 'REVIEW', 'DECLINE')),
    CONSTRAINT chk_decision_policy_adjusted CHECK (policy_adjusted_yn IN ('Y', 'N')),
    CONSTRAINT chk_decision_override_yn CHECK (override_yn IN ('Y', 'N'))
);

CREATE INDEX idx_decision_result_application_id ON decision_result (application_id);
CREATE INDEX idx_decision_result_prediction_id ON decision_result (prediction_id);

CREATE TABLE decision_rule_hit (
    id           BIGSERIAL PRIMARY KEY,
    decision_id  BIGINT NOT NULL REFERENCES decision_result (id) ON DELETE CASCADE,
    rule_id      BIGINT NOT NULL REFERENCES risk_policy_rule (id) ON DELETE RESTRICT,
    matched      BOOLEAN NOT NULL DEFAULT TRUE,
    detail       JSONB,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_decision_rule_hit_decision_id ON decision_rule_hit (decision_id);
CREATE INDEX idx_decision_rule_hit_rule_id ON decision_rule_hit (rule_id);
