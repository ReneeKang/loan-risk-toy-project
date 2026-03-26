# 아키텍처 (Loan Risk Toy Project)

이 문서는 저장소에 포함되는 **아키텍처 개요**이다. 상세 파이프라인·진행 기록은 로컬 `docs/`의 다른 파일을 참고한다.

## 레이어 개요

| 레이어 | 역할 |
|--------|------|
| API (`app/`) | FastAPI, 라우터, 설정, DB 세션 |
| 데이터 | PostgreSQL — raw → clean → feature → prediction/decision |
| 배치 | `scripts/` — 적재, 피처 빌드, 모델 학습 |
| 모델 | `ml/artifacts/` — 학습 산출물 (저장소에는 보통 미포함, `.gitignore` 참고) |

## 주요 디렉터리

- `app/core/` — 설정(`config`), DB(`database`)
- `app/models/` — SQLAlchemy ORM
- `app/routers/`, `app/schemas/` — HTTP·Pydantic
- `app/services/`, `app/repositories/` — 비즈니스·DB 접근
- `sql/` — DDL 및 보조 마이그레이션 스크립트

## 데이터 흐름 (요약)

1. 원천 CSV → `loan_application_raw` / `loan_application_clean`
2. 정제 데이터 → `loan_application_feature` (`model_input_json` 등)
3. 학습 → LightGBM 아티팩트 + `model_registry`

추가로 SHAP·LLM은 PRD 범위이며, API·테이블은 단계적으로 확장 가능하다.
