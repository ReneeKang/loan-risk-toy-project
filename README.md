# Loan Risk Toy Project

## 개요
Lending Club 데이터를 기반으로 대출 연체 위험을 예측하고,
정책 기반 의사결정 + SHAP + LLM까지 포함한 금융권 신용리스크 시스템 축소판 프로젝트.

## 주요 기능
- 대출 신청 데이터 등록
- 머신러닝 기반 부실 예측
- 정책 기반 승인/거절/추가심사 결정
- SHAP 설명
- LLM 심사 코멘트 생성

## 실행 방법
1. PostgreSQL 실행
2. SQL DDL 적용
3. 데이터 적재
4. 모델 학습
5. FastAPI 실행

## 기술 스택
- FastAPI
- PostgreSQL
- LightGBM
- SHAP
- OpenAI API

## 아키텍처
docs/architecture.md 참고
