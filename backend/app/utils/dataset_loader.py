import io
import os
import uuid
from typing import Iterable, List, Tuple

import pandas as pd
from fastapi import HTTPException, UploadFile
from starlette import status

from app.core.config import settings


REQUIRED_COLUMNS = {"question", "standard_answer"}
OPTIONAL_COLUMNS = {"question_id", "system_prompt", "user_context"}
SUPPORTED_EXTENSIONS = {".csv", ".xls", ".xlsx"}


def _guess_extension(filename: str | None) -> str:
    if not filename:
        return ""
    return os.path.splitext(filename)[1].lower()


def _validate_extension(extension: str) -> None:
    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "DATASET_UNSUPPORTED_FORMAT",
                "message": "仅支持 CSV 或 Excel 格式文件",
            },
        )


def _validate_filesize(raw: bytes) -> None:
    max_bytes = settings.max_dataset_file_size_mb * 1024 * 1024
    if len(raw) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "code": "DATASET_TOO_LARGE",
                "message": f"文件大小不能超过 {settings.max_dataset_file_size_mb}MB",
            },
        )


def _load_dataframe(extension: str, raw: bytes) -> pd.DataFrame:
    if extension == ".csv":
        return pd.read_csv(
            io.BytesIO(raw),
            dtype=str,
            encoding="utf-8",
            keep_default_na=False,
        )
    engine = "openpyxl" if extension == ".xlsx" else "xlrd"
    return pd.read_excel(
        io.BytesIO(raw),
        dtype=str,
        engine=engine,
    ).fillna("")


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    normalized = {col: col.strip().lower() for col in df.columns}
    df = df.rename(columns=normalized)
    return df


def _ensure_required_columns(df: pd.DataFrame) -> None:
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "DATASET_SCHEMA_INVALID",
                "message": "文件缺少 question 或 standard_answer 列",
            },
        )


def _sanitize_rows(df: pd.DataFrame) -> pd.DataFrame:
    df = df.where(pd.notnull(df), "")
    df["question"] = df["question"].astype(str).str.strip()
    df["standard_answer"] = df["standard_answer"].astype(str).str.strip()
    df = df[df["question"] != ""]
    df = df.reset_index(drop=True)
    return df


def _ensure_row_limit(df: pd.DataFrame) -> None:
    rows = len(df.index)
    if rows == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "DATASET_EMPTY", "message": "文件没有有效的问题数据"},
        )
    if rows > settings.max_dataset_rows:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "DATASET_TOO_MANY_ROWS",
                "message": f"文件最多支持 {settings.max_dataset_rows} 行",
            },
        )


def _assign_question_ids(df: pd.DataFrame) -> pd.DataFrame:
    if "question_id" not in df.columns:
        df["question_id"] = [str(uuid.uuid4()) for _ in df.index]
    else:
        df["question_id"] = df["question_id"].apply(lambda x: str(x).strip() or str(uuid.uuid4()))
        duplicates = df["question_id"][df["question_id"].duplicated()].unique()
        if len(duplicates):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "DATASET_DUPLICATE_QUESTION_ID",
                    "message": "question_id 存在重复值，请确认后重试",
                },
            )
    return df


def _select_columns(df: pd.DataFrame) -> pd.DataFrame:
    cols = list(REQUIRED_COLUMNS | OPTIONAL_COLUMNS)
    existing = [col for col in cols if col in df.columns]
    return df[existing]


def dataset_to_records(df: pd.DataFrame) -> List[dict]:
    df = _sanitize_rows(df)
    _ensure_row_limit(df)
    df = _assign_question_ids(df)
    df = _select_columns(df)
    records = df.to_dict(orient="records")
    for record in records:
        record.setdefault("system_prompt", None)
        record.setdefault("user_context", None)
    return records


async def load_dataset(upload: UploadFile) -> Tuple[List[dict], bytes]:
    extension = _guess_extension(upload.filename)
    _validate_extension(extension)

    raw = await upload.read()
    _validate_filesize(raw)

    df = _load_dataframe(extension, raw)
    df = _normalize_columns(df)
    _ensure_required_columns(df)
    records = dataset_to_records(df)
    return records, raw
