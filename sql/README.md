# SQL layout and change policy

## Canonical DDL

- **`000_create_database.sql`** — Creates database `loan_risk` (run once against `postgres` if needed).
- **`001_schema.sql`** — **Single source of truth** for a fresh database. Apply to `loan_risk` after creation.

## Incremental migrations (existing DBs only)

Older snapshots may need:

| File | Purpose |
|------|---------|
| `002_lending_club_raw_clean.sql` | Placeholder note; superseded by `001_schema.sql`. |
| `004_add_model_input_json.sql` | Adds `model_input_json` if the table predates it. |
| `005_add_prediction_predicted_default_yn.sql` | Adds `predicted_default_yn` if `prediction_result` predates it. |

Skip a migration if `001_schema.sql` already defines the same columns/constraints.

## Frozen core tables (roles do not change)

| Table | Role |
|-------|------|
| `loan_application_raw` | Source ingestion only (`raw_payload`, line identity). |
| `loan_application_clean` | Normalized application; **`target_default_yn` is `Y` or `N` only.** |
| `loan_application_feature` | **`model_input_json`** = official model input; versioned by `feature_version`. |
| `model_registry` | Trained model metadata, `artifact_uri`, linked `feature_version`. |
| `prediction_result` | Official outputs: **`risk_score`**, **`predicted_default_yn`**, **`risk_grade`**. |

## How to change the schema later

- **Do not** redefine these tables’ roles; extend with **new columns** or **new tables**.
- Add a new numbered file: `sql/NNN_short_description.sql` (e.g. `ALTER TABLE ... ADD COLUMN ...`).
