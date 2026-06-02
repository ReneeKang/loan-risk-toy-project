# 아키텍처 v3 (Loan Risk Toy Project)

> **통합본:** [`architecture_unified.md`](architecture_unified.md)에 본 스냅샷이 반영·갱신되었다(예: explanations·reviews API). 새로 읽을 때는 통합본을 우선한다.

**v2**(`architecture_v2.md`)의 PRD·도메인 배경은 그대로 두고, **현재 저장소에 실제로 구현된 런타임·API·정책**을 반영한 스냅샷 문서다. 상세 PRD 원문은 로컬 `loan_risk_toy_project_prd.md`를 본다.

---

## v2 대비 변경 요약


| 구분                      | v2 시점                  | v3 (현재 구현)                                                                      |
| ----------------------- | ---------------------- | ------------------------------------------------------------------------------- |
| 예측 API                  | 목표 수준                  | `POST/GET /api/v1/predictions`, `prediction_result` 저장                          |
| 정책·심사 결정                | 스키마 위주                 | **정책 엔진** + `POST/GET /api/v1/decisions`, `decision_result`·`decision_rule_hit` |
| 정책 룰 마스터                | 테이블만                   | `sql/006_seed_policy_rules.sql`로 *POLICY_ 3건** 시드                               |
| `decision_result` 값 도메인 | PRD 예: `MANUAL_REVIEW` | 구현은 `**APPROVE` / `REVIEW` / `DECLINE`** (`sql/001_schema.sql` CHECK)           |
| 운영                      | —                      | 콘솔 로깅(`LOG_LEVEL`), Swagger 한글 설명, `sql/README.md` 변경 정책                        |


---

## 1. 엔드투엔드 흐름 (구현 기준)


| 단계         | 상태        | 비고                                                              |
| ---------- | --------- | --------------------------------------------------------------- |
| 01 원천      | 구현        | Lending Club CSV → raw / clean (`scripts/load_raw_data.py`)     |
| 02 수집·전처리  | 구현        | `preprocessing_service`, `target_default_yn` Y/N                |
| 03 저장소     | 구현        | raw / clean / feature / `model_registry`                        |
| 04 ML      | 구현        | 피처 빌드(`build_features`), LightGBM 학습(`train_model`), 아티팩트·레지스트리 |
| 04b 예측 서빙  | 구현        | `prediction_service` → `prediction_result`                      |
| 05 정책·의사결정 | **부분 구현** | 점수 구간 + 3개 POLICY 룰 → `final_decision`; Override·수동 심사 UI는 없음   |
| 06 설명·LLM  | 미구현       | PRD 3차                                                          |
| 07 서비스     | 부분        | 아래 **§3 API 표** 참고                                              |


---

## 2. 정책 엔진 (구현 상세)

입력은 `**prediction_id`** 하나. 내부적으로:

1. `prediction_result`에서 `risk_score`, `feature_id` 등 조회
2. 동일 피처 행의 **`model_input_json`**에서 다음 필드 사용
  - `loan_amount_to_income_ratio`  
  - `high_dti_flag` (Y/N)  
  - `prior_delinquency_flag` (Y/N)

### 2.1 점수만으로 1차 판정 (`score_based_decision`)


| 조건                       | 결과        |
| ------------------------ | --------- |
| `risk_score` < 0.4       | `APPROVE` |
| 0.4 ≤ `risk_score` < 0.7 | `REVIEW`  |
| `risk_score` ≥ 0.7       | `DECLINE` |


> PRD §5의 **리스크 등급 A~E**(0.2 단위 구간)는 **예측 결과의 `risk_grade`** 쪽 개념과 가깝고, 정책 엔진의 **APPROVE/REVIEW/DECLINE** 구간(0.4/0.7)은 **별도 파라미터**로 둔다.

### 2.2 정책 룰 (`risk_policy_rule` + `decision_rule_hit`)

`sql/006_seed_policy_rules.sql`에 정의된 **3건**이 마스터에 있어야 하며, 코드는 `POLICY_HIGH_DTI`, `POLICY_PRIOR_DELINQ`, `POLICY_HIGH_LTI` 로 조회한다. 누락 시 `POST /decisions`는 **503**에 가깝게 처리(서비스 불가).


| 룰 코드                  | 조건(요약)                              | 효과               |
| --------------------- | ----------------------------------- | ---------------- |
| `POLICY_PRIOR_DELINQ` | `prior_delinquency_flag = Y`        | 최소 `**DECLINE`** |
| `POLICY_HIGH_DTI`     | `high_dti_flag = Y`                 | 최소 `**REVIEW`**  |
| `POLICY_HIGH_LTI`     | `loan_amount_to_income_ratio` ≥ 0.7 | 최소 `**REVIEW**`  |


최종 심각도는 **DECLINE > REVIEW > APPROVE** 로 병합한다. 점수 구간 결과와 다르면 `policy_adjusted_yn = Y`.

### 2.3 `decision_result` 저장 필드 (요지)

- `system_decision` / `score_based_decision`: 점수 구간만 반영한 값(동일하게 둠)  
- `final_decision`: 룰 반영 후  
- `policy_adjusted_yn`, `decision_reason_summary`  
- `override_yn = N`, `decided_by = system` (시스템 자동)  
- 동일 `prediction_id`당 **한 건**(`UNIQUE`); 중복 생성 시 **409** + 기존 본문

---

## 3. HTTP API (실제 라우트)


| 메서드    | 경로                                    | 역할                             |
| ------ | ------------------------------------- | ------------------------------ |
| `GET`  | `/health`, `/health/db`               | 앱·DB 헬스                        |
| `POST` | `/api/v1/predictions`                 | 단건 예측·`prediction_result` 저장   |
| `GET`  | `/api/v1/predictions/{prediction_id}` | 예측 조회                          |
| `POST` | `/api/v1/decisions`                   | 심사 결정 생성(`prediction_id` body) |
| `GET`  | `/api/v1/decisions/{decision_id}`     | 심사 결정·룰 히트 조회                  |


PRD에 있던 `loan-applications`, `explanations`, `llm-reviews`, `policy-rules` 조회 API 등은 **아직 없음**.

---

## 4. 저장소·배치 스크립트 (핵심만)


| 경로                  | 역할                                                                                          |
| ------------------- | ------------------------------------------------------------------------------------------- |
| `app/services/`     | `ingestion`, `preprocessing`, `feature`, `model`, `prediction`, `**policy_engine_service`** |
| `app/repositories/` | application, feature, health, prediction, `**decision`**                                    |
| `app/routers/`      | health, predictions, **decisions**                                                          |
| `scripts/`          | `load_raw_data.py`, `build_features.py`, `train_model.py`                                   |
| `sql/`              | `001_schema.sql` 기준 DDL; `006` 정책 시드; 변경 정책은 `sql/README.md`                                |


---

## 5. 스키마·문서 거버넌스

- 핵심 테이블 역할 고정·마이그레이션만 추가하는 원칙은 **v2 §5.1**과 동일.  
- 원격 저장소에 올리는 문서는 `.gitignore` 예외로 `architecture.md`, `**architecture_v2.md`**, `**architecture_v3.md`** 등만 포함하는 식으로 관리할 수 있다(팀 설정에 따름).

---

## 6. 미구현·확장 (PRD 대비)

- SHAP / `explanation_result`  
- LLM 코멘트 / `llm_review_result`  
- 심사자 **Override** API·`override_yn = Y` 흐름  
- `POST /api/v1/loan-applications` 등 신청 접수 API  
- PRD 스타일 공통 응답 래퍼(`resultCode` 등)

---

## 7. 참고 문서

- `[architecture.md](architecture.md)` — 짧은 개요·스키마 고정 링크  
- `[architecture_v2.md](architecture_v2.md)` — PRD 정렬·1·2·3차 범위  
- `[sql/README.md](../sql/README.md)` — DDL 적용 순서·`006` 시드 설명

