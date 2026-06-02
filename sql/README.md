# SQL layout and change policy

## Canonical DDL

- **`000_create_database.sql`** — Creates database `loan_risk` (run once against `postgres` if needed).
- **`001_schema.sql`** — **Single source of truth** for a fresh database. Apply to `loan_risk` after creation. (Includes inline `--` comments.)
- **`001_schema_comment_version.sql`** — **Optional.** Run after `001_schema.sql` to attach PostgreSQL `COMMENT ON TABLE/COLUMN` metadata in **English** (visible in `psql \d+`). Does not alter schema objects.
- **`001_schema_comment_version_ko.sql`** — **Optional.** Same as above with **Korean** `COMMENT` text; run after `001_schema.sql`. If both EN and KO are applied, the **last** file wins for each object.

## Incremental migrations (existing DBs only)

Older snapshots may need:

| File | Purpose |
|------|---------|
| `002_lending_club_raw_clean.sql` | Placeholder note; superseded by `001_schema.sql`. |
| `004_add_model_input_json.sql` | Adds `model_input_json` if the table predates it. |
| `005_add_prediction_predicted_default_yn.sql` | Adds `predicted_default_yn` if `prediction_result` predates it. |
| `006_seed_policy_rules.sql` | Inserts default `risk_policy_rule` rows for the policy engine (`POLICY_*`). Run after `001` before calling `POST /api/v1/decisions`. |
| `007_explanation_result.sql` | Adds `explanation_result` if the DB predates it (SHAP explanations). Fresh `001_schema.sql` installs include this table. |
| `008_llm_review_result.sql` | Adds `llm_review_result` (LLM 심사 코멘트). Fresh `001_schema.sql` includes it. |

Skip a migration if `001_schema.sql` already defines the same columns/constraints.

**Policy engine:** `decision_result` uses `APPROVE` / `REVIEW` / `DECLINE` (not `MANUAL_REVIEW`). Fresh installs get this from `001_schema.sql`; legacy DBs may need a manual `ALTER` to match `001`.

## Frozen core tables (roles do not change)

| Table | Role |
|-------|------|
| `loan_application_raw` | Source ingestion only (`raw_payload`, line identity). |
| `loan_application_clean` | Normalized application; **`target_default_yn` is `Y` or `N` only.** |
| `loan_application_feature` | **`model_input_json`** = official model input; versioned by `feature_version`. |
| `model_registry` | Trained model metadata, `artifact_uri`, linked `feature_version`. |
| `prediction_result` | Official outputs: **`risk_score`**, **`predicted_default_yn`**, **`risk_grade`**. |
| `explanation_result` | Optional SHAP top features per **`prediction_id`** (`feature_name`, `shap_value`, `rank`). |
| `llm_review_result` | LLM 생성 **심사 코멘트** (`review_comment`), `prediction_id`당 1건. |

## How to change the schema later

- **Do not** redefine these tables’ roles; extend with **new columns** or **new tables**.
- Add a new numbered file: `sql/NNN_short_description.sql` (e.g. `ALTER TABLE ... ADD COLUMN ...`).
