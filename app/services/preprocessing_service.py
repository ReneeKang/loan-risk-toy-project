from __future__ import annotations

"""Clean-layer transforms. Binary (0/1) targets for ML belong in feature/model stages."""

import re
from datetime import date
from decimal import Decimal
from typing import Any, Literal

import numpy as np
import pandas as pd

REQUIRED_COLUMNS: tuple[str, ...] = (
    "id",
    "loan_amnt",
    "int_rate",
    "term",
    "grade",
    "home_ownership",
    "emp_length",
    "dti",
    "delinq_2yrs",
    "revol_bal",
    "loan_status",
    "annual_inc",
    "issue_d",
)

TARGET_FULLY_PAID = "fully paid"
TARGET_CHARGED_OFF = "charged off"
TARGET_DEFAULT = "default"


def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip().lower().replace(" ", "_") for c in out.columns]
    return out


def remove_summary_rows(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "id" not in df.columns:
        return df
    numeric_id = pd.to_numeric(df["id"], errors="coerce")
    return df.loc[numeric_id.notna()].copy()


def normalize_loan_status(value: Any) -> str:
    return str(value).strip().lower()


def classify_target_default_yn(loan_status: Any) -> Literal["Y", "N"] | None:
    """Y/N label for default; ML 0/1 is derived later in feature/model stages."""
    s = normalize_loan_status(loan_status)
    if s == TARGET_FULLY_PAID:
        return "N"
    if s in (TARGET_CHARGED_OFF, TARGET_DEFAULT):
        return "Y"
    return None


def filter_target_rows(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "loan_status" not in df.columns:
        return df.iloc[0:0].copy()
    mask = df["loan_status"].map(classify_target_default_yn).notna()
    return df.loc[mask].copy()


def format_application_id(value: Any) -> str:
    v = pd.to_numeric(value, errors="coerce")
    if pd.isna(v):
        return ""
    f = float(v)
    if abs(f - round(f)) < 1e-9:
        return str(int(round(f)))
    return str(f)


def parse_term_months(term: Any) -> int | None:
    if pd.isna(term):
        return None
    m = re.search(r"(\d+)", str(term))
    if not m:
        return None
    return int(m.group(1))


def parse_percentage_float(value: Any) -> float | None:
    if pd.isna(value):
        return None
    if isinstance(value, str):
        s = value.strip().rstrip("%").strip()
        if s == "":
            return None
        return float(s)
    return float(value)


def parse_optional_int(value: Any) -> int | None:
    if pd.isna(value):
        return None
    return int(float(value))


def parse_optional_float(value: Any) -> float | None:
    if pd.isna(value):
        return None
    if isinstance(value, str):
        s = value.strip().rstrip("%").strip()
        if s == "":
            return None
        return float(s)
    return float(value)


def parse_issue_date(value: Any) -> date | None:
    if pd.isna(value):
        return None
    ts = pd.to_datetime(value, format="%b-%Y", errors="coerce")
    if pd.isna(ts):
        ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return None
    return ts.date()


def row_to_json_payload(row: pd.Series) -> dict[str, Any]:
    """Serialize a CSV row for JSONB storage (pandas/numpy safe)."""
    d: dict[str, Any] = {}
    for key, val in row.items():
        if str(key).startswith("_"):
            continue
        if pd.isna(val):
            d[str(key)] = None
        elif isinstance(val, pd.Timestamp):
            d[str(key)] = val.isoformat()
        elif isinstance(val, (np.integer,)):
            d[str(key)] = int(val)
        elif isinstance(val, (np.floating,)):
            d[str(key)] = float(val)
        elif isinstance(val, (np.bool_,)):
            d[str(key)] = bool(val)
        elif isinstance(val, (str, int, float, bool)):
            d[str(key)] = val
        else:
            d[str(key)] = str(val)
    return d


def prepare_clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Type cleanup, median fill for numeric fields used in clean layer.
    Expects target-filtered rows with REQUIRED_COLUMNS and _source_row_no.
    """
    if df.empty:
        return df
    out = df.copy()
    out["_application_id"] = out["id"].map(format_application_id)

    out["int_rate"] = out["int_rate"].map(parse_percentage_float)
    out["term_months"] = out["term"].map(parse_term_months)
    out["issue_d_parsed"] = out["issue_d"].map(parse_issue_date)
    out["dti"] = out["dti"].map(parse_optional_float)
    out["annual_inc"] = out["annual_inc"].map(parse_optional_float)
    out["loan_amnt"] = out["loan_amnt"].map(parse_optional_float)
    out["revol_bal"] = out["revol_bal"].map(parse_optional_float)
    out["delinq_2yrs"] = out["delinq_2yrs"].map(parse_optional_int)
    med_d = out["delinq_2yrs"].median()
    if pd.isna(med_d):
        out["delinq_2yrs"] = out["delinq_2yrs"].fillna(0).astype(int)
    else:
        out["delinq_2yrs"] = out["delinq_2yrs"].fillna(int(med_d)).astype(int)

    for col in ("grade", "home_ownership", "emp_length", "loan_status"):
        if col in out.columns:
            out[col] = (
                out[col]
                .fillna("")
                .map(lambda x: str(x).strip() if x is not None else "")
            )

    numeric_fill = ["int_rate", "dti", "annual_inc", "loan_amnt", "revol_bal"]
    for col in numeric_fill:
        if col not in out.columns:
            continue
        med = out[col].median()
        if pd.isna(med):
            out[col] = out[col].fillna(0.0)
        else:
            out[col] = out[col].fillna(med)

    if "term_months" in out.columns:
        med_t = out["term_months"].median()
        if pd.isna(med_t):
            out["term_months"] = out["term_months"].fillna(0).astype(int)
        else:
            out["term_months"] = out["term_months"].fillna(int(med_t)).astype(int)

    out["target_default_yn"] = out["loan_status"].map(classify_target_default_yn)
    return out


def assert_required_columns(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        msg = f"Missing required columns: {missing}"
        raise ValueError(msg)


def to_decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, (float, np.floating)) and np.isnan(float(value)):
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def build_clean_row(
    row: pd.Series,
    raw_id: int | None,
) -> dict[str, Any]:
    """ORM-compatible dict for LoanApplicationClean (subset of columns filled)."""
    tid = row["_application_id"]
    if not tid:
        raise ValueError("application_id is empty")

    issue_raw = row.get("issue_d_parsed")
    issue: date | None
    if issue_raw is None or pd.isna(issue_raw):
        issue = None
    elif isinstance(issue_raw, date):
        issue = issue_raw
    else:
        issue = parse_issue_date(issue_raw)

    tyn = row.get("target_default_yn")
    if tyn not in ("Y", "N"):
        raise ValueError("target_default_yn must be Y or N")

    return {
        "application_id": tid,
        "raw_id": raw_id,
        "loan_amnt": to_decimal_or_none(row.get("loan_amnt")),
        "term": None,
        "term_months": int(row["term_months"]) if pd.notna(row.get("term_months")) else None,
        "int_rate": to_decimal_or_none(row.get("int_rate")),
        "grade": row.get("grade") or None,
        "emp_length": row.get("emp_length") or None,
        "home_ownership": row.get("home_ownership") or None,
        "annual_inc": to_decimal_or_none(row.get("annual_inc")),
        "issue_d": issue,
        "loan_status": row.get("loan_status") or None,
        "dti": to_decimal_or_none(row.get("dti")),
        "delinq_2yrs": int(row["delinq_2yrs"]) if pd.notna(row.get("delinq_2yrs")) else None,
        "revol_bal": to_decimal_or_none(row.get("revol_bal")),
        "target_default_yn": tyn,
    }
