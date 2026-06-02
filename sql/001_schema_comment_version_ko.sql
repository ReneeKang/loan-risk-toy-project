-- =============================================================================
-- PostgreSQL COMMENT ON (한글 메타데이터 — psql \d+ / pg_catalog).
--
-- 적용 순서: 001_schema.sql 적용 **이후** 실행.
-- 영문 버전(001_schema_comment_version.sql)과 택1 또는 나중에 덮어쓰기 가능.
-- 재실행 안전: COMMENT는 이전 내용을 덮어씀. 스키마 객체는 변경하지 않음.
-- =============================================================================

COMMENT ON TABLE loan_application_raw IS '원천 적재 전용: CSV 한 줄당 한 행; source_system + 파일명 + 행번호로 유일성.';
COMMENT ON COLUMN loan_application_raw.raw_id IS '대리 키(서로게이트 PK).';
COMMENT ON COLUMN loan_application_raw.application_id IS '원천 페이로드의 신청 ID(선택, 이 테이블에서는 유니크 아님).';
COMMENT ON COLUMN loan_application_raw.source_system IS '데이터 소스 식별자(예: lending_club).';
COMMENT ON COLUMN loan_application_raw.source_file_name IS '중복 방지용 원본 파일명.';
COMMENT ON COLUMN loan_application_raw.source_row_no IS '해당 파일 내 1부터 시작하는 행 번호.';
COMMENT ON COLUMN loan_application_raw.raw_payload IS '원천 행 전체 JSONB.';
COMMENT ON COLUMN loan_application_raw.ingested_at IS '적재 시각(UTC).';

COMMENT ON TABLE loan_application_clean IS '정제된 대출 신청; PK는 application_id; 라벨은 target_default_yn Y/N.';
COMMENT ON COLUMN loan_application_clean.target_default_yn IS '학습용 역사 라벨 Y/N만 저장(0/1은 ML 코드에서 파생, clean에 미저장).';
COMMENT ON COLUMN loan_application_clean.raw_id IS '연결 가능 시 원천 raw 행 FK.';

COMMENT ON TABLE loan_application_feature IS 'application_id·feature_version 단위 피처 행; 공식 모델 입력은 model_input_json.';
COMMENT ON COLUMN loan_application_feature.model_input_json IS '학습·온라인 추론에 쓰는 공식 피처 딕셔너리.';
COMMENT ON COLUMN loan_application_feature.features IS '동일 스냅샷·확장 JSON(선택); ML은 model_input_json 우선.';

COMMENT ON TABLE model_registry IS '등록된 학습 모델: 경로, 지표, 연결된 feature_version.';
COMMENT ON COLUMN model_registry.artifact_uri IS '직렬화 모델 파일 경로(예: joblib).';
COMMENT ON COLUMN model_registry.is_active IS '운영 플래그; 학습 파이프라인이 구버전 비활성화 가능.';

COMMENT ON TABLE prediction_result IS '모델 예측 한 건: 점수, 등급, 임계값 기반 부실 여부.';
COMMENT ON COLUMN prediction_result.risk_score IS '양성 클래스(부실) 확률 추정치, 범위 [0,1].';
COMMENT ON COLUMN prediction_result.risk_grade IS '점수 구간에 따른 등급 A~E.';
COMMENT ON COLUMN prediction_result.predicted_default_yn IS '점수 임계(예: 0.5) 기준 Y/N; clean의 target_default_yn과는 별개.';

COMMENT ON TABLE risk_policy_rule IS '정책 룰 마스터; POLICY_* 코드는 006_seed_policy_rules.sql로 시드.';
COMMENT ON COLUMN risk_policy_rule.rule_code IS '애플리케이션에서 쓰는 고정 코드(예: POLICY_HIGH_DTI).';
COMMENT ON COLUMN risk_policy_rule.priority IS '향후 엔진에서 낮을수록 우선 평가 가능; 현재 엔진은 고정 로직.';

COMMENT ON TABLE decision_result IS '정책 엔진 결과; prediction_id당 최대 1건(UNIQUE).';
COMMENT ON COLUMN decision_result.score_based_decision IS 'risk_score 구간만 반영한 판정(APPROVE/REVIEW/DECLINE).';
COMMENT ON COLUMN decision_result.final_decision IS '정책 룰 적용 후 최종 판정.';
COMMENT ON COLUMN decision_result.policy_adjusted_yn IS 'final이 score_based와 다르면 Y.';
COMMENT ON COLUMN decision_result.decided_by IS '자동이면 system; 향후 수동 심사자 식별자.';

COMMENT ON TABLE decision_rule_hit IS '감사: final_decision 산출 시 매칭된 risk_policy_rule 이력.';
COMMENT ON COLUMN decision_rule_hit.detail IS '룰 매칭 시점 입력 스냅샷 JSON.';
