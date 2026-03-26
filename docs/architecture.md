# 아키텍처 (Loan Risk Toy Project)

이 문서는 저장소에 포함되는 **아키텍처 개요**이다. 상세 파이프라인·진행 기록은 로컬 `docs/`의 다른 파일을 참고한다.

## 레이어 개요

| 레이어 | 역할 |
|--------|------|
| API (`app/`) | FastAPI, 라우터, 설정, DB 세션 |
| 데이터 | PostgreSQL — raw → clean → feature → prediction/decision |
| 배치 | `scripts/` — 적재, 피처 빌드, 모델 학습 |
| 모델 | `ml/artifacts/` — 학습 산출물 (저장소에는 보통 미포함, `.gitignore` 참고) |

## 스키마 고정 원칙

핵심 테이블(`raw` / `clean` / `feature` / `model_registry` / `prediction_result`)의 **역할은 변경하지 않는다**.

- **clean**: `target_default_yn` = Y/N  
- **feature**: 공식 모델 입력 = **`model_input_json`**  
- **prediction_result**: 공식 결과 = **`risk_score`**, **`predicted_default_yn`**, **`risk_grade`**  
- 이후 변경은 **컬럼 추가** 또는 **`sql/NNN_*.sql` 마이그레이션**만 사용한다.

상세: [`sql/README.md`](../sql/README.md), [`sql/001_schema.sql`](../sql/001_schema.sql) 헤더 주석.

## 주요 디렉터리

- `app/core/` — 설정(`config`), DB(`database`)
- `app/models/` — SQLAlchemy ORM
- `app/routers/`, `app/schemas/` — HTTP·Pydantic
- `app/services/`, `app/repositories/` — 비즈니스·DB 접근
- `sql/` — DDL 및 보조 마이그레이션 스크립트 (`README.md`에 변경 정책)

## 데이터 흐름 (요약)

1. 원천 CSV → `loan_application_raw` / `loan_application_clean`
2. 정제 데이터 → `loan_application_feature` (**공식 입력: `model_input_json`**)
3. 학습 → LightGBM 아티팩트 + `model_registry`

추가로 SHAP·LLM은 PRD 범위이며, API·테이블은 단계적으로 확장 가능하다.
