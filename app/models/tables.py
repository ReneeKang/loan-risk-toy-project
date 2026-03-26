from __future__ import annotations

"""
ORM mapping for PostgreSQL.

Schema contract (frozen roles; extend via new columns / migrations only):
  - loan_application_raw: source ingestion
  - loan_application_clean: normalized rows; target_default_yn is Y or N
  - loan_application_feature: model_input_json is the official model input
  - model_registry: trained model metadata + artifact_uri
  - prediction_result: official outputs risk_score, predicted_default_yn, risk_grade

See sql/001_schema.sql and sql/README.md.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CHAR,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class LoanApplicationRaw(Base):
    """Source-only ingestion (raw_payload + source line identity)."""

    __tablename__ = "loan_application_raw"

    raw_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    application_id: Mapped[Optional[str]] = mapped_column(String(64))
    source_system: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=text("'lending_club'")
    )
    source_file_name: Mapped[str] = mapped_column(String(512), nullable=False)
    source_row_no: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    clean_rows: Mapped[list["LoanApplicationClean"]] = relationship(
        back_populates="raw",
    )


class LoanApplicationClean(Base):
    """Normalized application; training label target_default_yn is Y or N only."""

    __tablename__ = "loan_application_clean"

    application_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    raw_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("loan_application_raw.raw_id", ondelete="SET NULL"),
    )
    loan_amnt: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    term: Mapped[Optional[str]] = mapped_column(String(32))
    term_months: Mapped[Optional[int]] = mapped_column(Integer)
    int_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4))
    installment: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    grade: Mapped[Optional[str]] = mapped_column(String(8))
    sub_grade: Mapped[Optional[str]] = mapped_column(String(8))
    emp_title: Mapped[Optional[str]] = mapped_column(String(256))
    emp_length: Mapped[Optional[str]] = mapped_column(String(64))
    home_ownership: Mapped[Optional[str]] = mapped_column(String(32))
    annual_inc: Mapped[Optional[Decimal]] = mapped_column(Numeric(16, 2))
    verification_status: Mapped[Optional[str]] = mapped_column(String(32))
    issue_d: Mapped[Optional[date]] = mapped_column(Date)
    loan_status: Mapped[Optional[str]] = mapped_column(String(64))
    purpose: Mapped[Optional[str]] = mapped_column(String(128))
    zip_code: Mapped[Optional[str]] = mapped_column(String(16))
    addr_state: Mapped[Optional[str]] = mapped_column(String(8))
    dti: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4))
    delinq_2yrs: Mapped[Optional[int]] = mapped_column(Integer)
    earliest_cr_line: Mapped[Optional[date]] = mapped_column(Date)
    open_acc: Mapped[Optional[int]] = mapped_column(Integer)
    pub_rec: Mapped[Optional[int]] = mapped_column(Integer)
    revol_bal: Mapped[Optional[Decimal]] = mapped_column(Numeric(16, 2))
    revol_util: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4))
    total_acc: Mapped[Optional[int]] = mapped_column(Integer)
    target_default_yn: Mapped[str] = mapped_column(CHAR(1), nullable=False)
    cleaned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    raw: Mapped[Optional[LoanApplicationRaw]] = relationship(
        back_populates="clean_rows",
        foreign_keys=[raw_id],
    )
    features: Mapped[list["LoanApplicationFeature"]] = relationship(
        back_populates="clean",
    )


class LoanApplicationFeature(Base):
    """Feature row per feature_version; model_input_json is the official model input."""

    __tablename__ = "loan_application_feature"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    application_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("loan_application_clean.application_id", ondelete="CASCADE"),
        nullable=False,
    )
    feature_version: Mapped[str] = mapped_column(String(64), nullable=False)
    # Snapshot / extended JSON; training and inference must use model_input_json.
    features: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    model_input_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    clean: Mapped[LoanApplicationClean] = relationship(
        back_populates="features",
    )
    predictions: Mapped[list["PredictionResult"]] = relationship(
        back_populates="feature_row",
    )


class ModelRegistry(Base):
    """Registered model metadata; links feature_version to artifact_uri."""

    __tablename__ = "model_registry"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    algorithm: Mapped[str] = mapped_column(String(64), nullable=False)
    feature_version: Mapped[str] = mapped_column(String(64), nullable=False)
    auc: Mapped[Optional[Decimal]] = mapped_column(Numeric(7, 6))
    recall: Mapped[Optional[Decimal]] = mapped_column(Numeric(7, 6))
    precision_: Mapped[Optional[Decimal]] = mapped_column("precision", Numeric(7, 6))
    artifact_uri: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    trained_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    predictions: Mapped[list["PredictionResult"]] = relationship(
        back_populates="model",
    )


class PredictionResult(Base):
    """Model output row; official columns: risk_score, predicted_default_yn, risk_grade."""

    __tablename__ = "prediction_result"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    application_id: Mapped[str] = mapped_column(String(64), nullable=False)
    feature_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("loan_application_feature.id", ondelete="RESTRICT"),
        nullable=False,
    )
    model_registry_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("model_registry.id", ondelete="RESTRICT"),
        nullable=False,
    )
    risk_score: Mapped[Decimal] = mapped_column(Numeric(10, 8), nullable=False)
    risk_grade: Mapped[str] = mapped_column(CHAR(1), nullable=False)
    predicted_default_yn: Mapped[str] = mapped_column(CHAR(1), nullable=False)
    predicted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    feature_row: Mapped[LoanApplicationFeature] = relationship(
        back_populates="predictions",
    )
    model: Mapped[ModelRegistry] = relationship(back_populates="predictions")
    decisions: Mapped[list["DecisionResult"]] = relationship(
        back_populates="prediction",
    )


class RiskPolicyRule(Base):
    __tablename__ = "risk_policy_rule"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    rule_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    rule_name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("100"))
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    condition_sql: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    rule_hits: Mapped[list["DecisionRuleHit"]] = relationship(
        back_populates="rule",
    )


class DecisionResult(Base):
    __tablename__ = "decision_result"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    application_id: Mapped[str] = mapped_column(String(64), nullable=False)
    prediction_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("prediction_result.id", ondelete="RESTRICT"),
        nullable=False,
    )
    system_decision: Mapped[str] = mapped_column(String(32), nullable=False)
    score_based_decision: Mapped[str] = mapped_column(String(32), nullable=False)
    final_decision: Mapped[str] = mapped_column(String(32), nullable=False)
    policy_adjusted_yn: Mapped[str] = mapped_column(CHAR(1), nullable=False)
    decision_reason_summary: Mapped[Optional[str]] = mapped_column(Text)
    override_yn: Mapped[str] = mapped_column(CHAR(1), nullable=False, server_default=text("'N'"))
    decided_by: Mapped[str] = mapped_column(String(64), nullable=False, server_default=text("'system'"))
    override_flag: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    overridden_by: Mapped[Optional[str]] = mapped_column(String(128))
    override_reason: Mapped[Optional[str]] = mapped_column(Text)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    prediction: Mapped[PredictionResult] = relationship(back_populates="decisions")
    rule_hits: Mapped[list["DecisionRuleHit"]] = relationship(
        back_populates="decision",
    )


class DecisionRuleHit(Base):
    __tablename__ = "decision_rule_hit"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    decision_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("decision_result.id", ondelete="CASCADE"),
        nullable=False,
    )
    rule_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("risk_policy_rule.id", ondelete="RESTRICT"),
        nullable=False,
    )
    matched: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    detail: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    decision: Mapped[DecisionResult] = relationship(back_populates="rule_hits")
    rule: Mapped[RiskPolicyRule] = relationship(back_populates="rule_hits")
