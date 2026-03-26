# 아키텍처 v2 (Loan Risk Toy Project)

`architecture.md`의 요약을 유지하면서, 설계 의도·도메인 규칙·확장 단계를 한곳에 모은 문서다. (상세 원문은 로컬 전용 `loan_risk_toy_project_prd.md`를 참고한다.)

---

## 1. 목표와 범위

- **비즈니스**: 차입자 연체/부실 가능성 예측 → **정책 룰과 결합**한 승인·추가심사·거절, 설명 가능성, 심사 코멘트까지 포함한 **금융권 신용리스크 심사 시스템 축소판**.
- **기술**: 배치 ETL + PostgreSQL + FastAPI + 모델/피처/정책 버전 분리를 지향한다.
- **캐글식과의 차이**: “CSV → 학습 → 정확도”가 아니라 **접수 → 정제·피처 → 점수 → 정책 → 최종 심사 → 설명·모니터링** 흐름을 전제로 한다.

---

## 2. 엔드투엔드 흐름 (PRD §4 요약)


| 단계         | 내용                                      |
| ---------- | --------------------------------------- |
| 01 원천      | Lending Club CSV, 신청·고객·`loan_status` 등 |
| 02 수집·전처리  | 결측/이상치, 컬럼 정제, 파생변수                     |
| 03 저장소     | Raw / Clean / Feature, 모델 메타, 예측·판정 이력  |
| 04 ML      | 부실 예측, 리스크 점수, 모델 버전                    |
| 05 정책·의사결정 | 등급·구간별 판정, 룰, Override                  |
| 06 설명·보조   | SHAP, LLM 심사 코멘트                        |
| 07 서비스     | 예측·의사결정·설명·코멘트·룰 API                    |
| 08 사용자     | 심사·분석·정책 담당                             |


현재 저장소 구현은 주로 **01~04 일부 + 배치 스크립트**에 가깝고, **05~07**은 스키마/확장 여지 위주다.

---

## 3. 핵심 설계 원칙

- **모델 점수 ≠ 최종 의사결정**: 점수는 입력으로 쓰고, **정책 룰·Override**로 최종 상태를 정한다.
- **엔티티 중심**: 핵심 단위는 **대출 신청(application)** 이며, 원천 → 정제 → 피처 → 예측 → 결정 → 설명·LLM으로 이어진다.

---

## 4. 비즈니스 규칙 요약 (PRD §5)

### 4.1 리스크 등급 (`risk_score` = 부실 확률 가정)


| 등급  | 점수 구간           |
| --- | --------------- |
| A   | 0.20 미만         |
| B   | 0.20 이상 0.40 미만 |
| C   | 0.40 이상 0.60 미만 |
| D   | 0.60 이상 0.80 미만 |
| E   | 0.80 이상         |


### 4.2 점수 기반 1차 판정(후보)

- A/B → 승인 후보  
- C/D → 추가심사 후보  
- E → 거절 후보

### 4.3 정책 룰 예시

- `delinq_2yrs >= 2` → 추가심사 또는 거절  
- `dti >= 30` → 추가심사  
- `loan_amount / annual_income >= 0.7` → 추가심사 또는 거절  
- 필수 입력 누락 → 자동 승인 금지

### 4.4 Override

- 심사자가 최종 상태 수동 변경 가능, **사유 필수**, 시스템 결정과 사람 결정 이력 분리 저장.

---

## 5. 데이터 모델 (논리 테이블)

PRD 기준 테이블과 역할이다. DDL은 `sql/001_schema.sql` 등과 대조한다.


| 테이블                        | 역할               |
| -------------------------- | ---------------- |
| `loan_application_raw`     | 원천 적재            |
| `loan_application_clean`   | 정제 신청 데이터        |
| `loan_application_feature` | 모델 입력 피처         |
| `model_registry`           | 모델·피처 버전·성능·아티팩트 |
| `prediction_result`        | 모델 예측(점수·등급)     |
| `risk_policy_rule`         | 정책 룰 마스터         |
| `decision_result`          | 최종 의사결정          |
| `decision_rule_hit`        | 적용 룰 이력          |
| `explanation_result`       | SHAP 설명 (확장)     |
| `llm_review_result`        | LLM 심사 코멘트 (확장)  |


---

## 6. 저장소 레이아웃 (목표 vs 현재)

PRD 권장 구조는 API·서비스·리포지토리·ML·배치·문서를 세분화한 형태다. 현재 repo는 그 **부분집합**으로 동작한다.

- **있는 것**: `app/core`, `models`, `schemas`, `routers`(health), `services`(ingestion, preprocessing, feature, model), `repositories`, `scripts/load_raw_data.py`, `build_features.py`, `train_model.py`, `sql/`, `ml/artifacts/`(바이너리는 `.gitignore`로 제외 가능).
- **PRD 대비 비어 있거나 얇은 것**: `prediction_service`, `policy_engine_service`, `explanation_service`, `llm_review_service`, 대응 라우터·리포지토리, 공통 응답 포맷, `docker-compose.yml` 등.

---

## 7. 구현 단계 (PRD §8)


| 차수     | 범위                                                |
| ------ | ------------------------------------------------- |
| **1차** | CSV 적재·전처리·PostgreSQL·피처·LightGBM·단건 예측 API·예측 저장 |
| **2차** | 정책 엔진, 최종 의사결정·룰 히트 저장                            |
| **3차** | SHAP·LLM 코멘트·설명 조회 API                            |


---

## 8. API 설계 원칙 (PRD §9 요약)

- 응답 포맷 통일, 단건 예측과 조회 분리.
- **모델 점수**와 **최종 심사 결과**를 동일 개념으로 취급하지 않는다.

**예시 엔드포인트 (목표)**

- `POST /api/v1/loan-applications`
- `POST /api/v1/predictions`
- `GET /api/v1/predictions/{predictionId}`
- `GET /api/v1/decisions/{decisionId}`
- `GET /api/v1/explanations/{predictionId}`
- `GET /api/v1/llm-reviews/{decisionId}`
- `GET /api/v1/policy-rules`

공통 응답 예: `resultCode`, `resultMessage`, `data` 래핑 (PRD 예시).

---

## 9. 서비스 레이어 책임 (PRD §10)


| 서비스                     | 책임                  |
| ----------------------- | ------------------- |
| `ingestion_service`     | raw CSV, raw 테이블 적재 |
| `preprocessing_service` | 정제, 결측, 타깃          |
| `feature_service`       | 파생변수, feature 테이블   |
| `model_service`         | 모델 로드·버전·예측         |
| `policy_engine_service` | 등급·룰·최종 상태          |
| `explanation_service`   | SHAP·설명 저장          |
| `llm_review_service`    | LLM 입력·프롬프트·의견 저장   |


---

## 10. 현재 코드베이스와의 연결 (`architecture.md` 보완)

1. **데이터 파이프**: 원천 → `loan_application_raw` / `loan_application_clean` → `loan_application_feature` → 학습·`model_registry`·아티팩트.
2. **API**: 운영 엔드포인트는 PRD 목록을 **목표**로 두고, 지금은 헬스·DB 연결 중심.
3. **문서**: 설계 전문은 저장소에 포함하지 않고 로컬 PRD로 둔다. 원격에는 본 문서와 `architecture.md`로 요약만 유지한다.

