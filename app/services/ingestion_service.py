from __future__ import annotations

"""
Ingestion: writes loan_application_raw (source) and loan_application_clean (normalized).
Does not change the schema roles of raw/clean; see sql/README.md.
"""

import logging
from pathlib import Path
from typing import Iterator, Literal

import pandas as pd
from sqlalchemy.orm import Session

from app.models.tables import LoanApplicationClean, LoanApplicationRaw
from app.repositories import application_repository as app_repo
from app.services import preprocessing_service as pre

logger = logging.getLogger(__name__)

ReadMode = Literal["sample", "chunk"]


def iter_lending_club_dataframes(
    csv_path: Path,
    mode: ReadMode,
    nrows: int,
    chunksize: int,
) -> Iterator[pd.DataFrame]:
    """
    Yield CSV data as DataFrames.
    - sample: single read with nrows (default 1000 for dev).
    - chunk: repeated reads with chunksize (default 10000).
    """
    path = Path(csv_path)
    if not path.is_file():
        msg = f"CSV file not found: {path}"
        raise FileNotFoundError(msg)

    if mode == "sample":
        df = pd.read_csv(path, nrows=nrows, low_memory=False)
        yield df
        return

    reader = pd.read_csv(path, chunksize=chunksize, low_memory=False)
    for chunk in reader:
        yield chunk


def process_dataframe_chunk(
    session: Session,
    df: pd.DataFrame,
    *,
    source_file_name: str,
    source_system: str,
    source_row_base: int,
) -> tuple[int, int]:
    """
    Insert into loan_application_raw (one row per source line; deduped by
    source_system + source_file_name + source_row_no) and loan_application_clean
    (Fully Paid / Charged Off / Default only, target_default_yn Y/N).

    source_row_base: 1-based row number in the CSV (first data row = 1) for the
    first row of this dataframe chunk.

    Returns counts (raw_inserted, clean_inserted).
    """
    if df.empty:
        return 0, 0

    work = pre.normalize_column_names(df)
    pre.assert_required_columns(work)
    work = work.copy()
    work["_source_row_no"] = [source_row_base + i for i in range(len(work))]
    work = pre.remove_summary_rows(work)
    if work.empty:
        return 0, 0

    work["_app_id"] = work["id"].map(pre.format_application_id)
    work = work[work["_app_id"] != ""]
    if work.empty:
        return 0, 0

    source_row_list = work["_source_row_no"].astype(int).tolist()
    existing_rows = app_repo.get_existing_source_row_nos(
        session,
        source_system,
        source_file_name,
        source_row_list,
    )

    to_insert_raw = work[~work["_source_row_no"].isin(existing_rows)]
    raw_rows: list[LoanApplicationRaw] = []
    for _, row in to_insert_raw.iterrows():
        payload = pre.row_to_json_payload(row.drop(labels=["_app_id", "_source_row_no"], errors="ignore"))
        app_id_val = str(row["_app_id"]) if row["_app_id"] else None
        raw_rows.append(
            LoanApplicationRaw(
                application_id=app_id_val,
                source_system=source_system,
                source_file_name=source_file_name,
                source_row_no=int(row["_source_row_no"]),
                raw_payload=payload,
            ),
        )

    raw_inserted = app_repo.insert_raw_batch(session, raw_rows)

    target_df = pre.filter_target_rows(work)
    if target_df.empty:
        session.flush()
        return raw_inserted, 0

    clean_prepared = pre.prepare_clean_dataframe(target_df)
    if clean_prepared.empty:
        return raw_inserted, 0

    needed_row_nos = clean_prepared["_source_row_no"].astype(int).tolist()
    raw_by_row = app_repo.get_raw_id_map_by_source_rows(
        session,
        source_system,
        source_file_name,
        needed_row_nos,
    )

    clean_ids = clean_prepared["_application_id"].unique().tolist()
    existing_clean = app_repo.get_existing_clean_application_ids(session, clean_ids)
    to_insert_clean = clean_prepared[
        ~clean_prepared["_application_id"].isin(existing_clean)
    ]

    clean_rows: list[LoanApplicationClean] = []
    for _, row in to_insert_clean.iterrows():
        sr = int(row["_source_row_no"])
        raw_id = raw_by_row.get(sr)
        if raw_id is None:
            logger.warning(
                "Missing raw row for source_row_no=%s; skipping clean",
                sr,
            )
            continue
        data = pre.build_clean_row(row, raw_id)
        clean_rows.append(LoanApplicationClean(**data))

    clean_inserted = app_repo.insert_clean_batch(session, clean_rows)
    return raw_inserted, clean_inserted


def run_ingestion(
    session: Session,
    csv_path: Path,
    mode: ReadMode,
    *,
    nrows: int = 1000,
    chunksize: int = 10000,
    source_system: str = "lending_club",
) -> tuple[int, int]:
    """
    Run full file ingestion. Returns total (raw_inserted, clean_inserted).
    """
    source_file_name = Path(csv_path).name
    total_raw = 0
    total_clean = 0
    data_row_offset = 0

    for chunk in iter_lending_club_dataframes(csv_path, mode, nrows, chunksize):
        source_row_base = data_row_offset + 1
        r, c = process_dataframe_chunk(
            session,
            chunk,
            source_file_name=source_file_name,
            source_system=source_system,
            source_row_base=source_row_base,
        )
        total_raw += r
        total_clean += c
        data_row_offset += len(chunk)
        session.commit()
        logger.info(
            "Committed chunk: raw_inserted=%s clean_inserted=%s (cumulative raw=%s clean=%s)",
            r,
            c,
            total_raw,
            total_clean,
        )

    return total_raw, total_clean
