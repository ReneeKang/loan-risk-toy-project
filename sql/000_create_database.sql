-- PostgreSQL 데이터베이스 생성 (슈퍼유저로 postgres DB에 연결한 뒤 실행)
--   psql -U postgres -d postgres -f sql/000_create_database.sql

CREATE DATABASE loan_risk
    WITH ENCODING 'UTF8'
    TEMPLATE template0;
