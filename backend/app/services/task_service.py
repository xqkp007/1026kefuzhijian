from __future__ import annotations

import json
import logging
from typing import Optional
from urllib.parse import urlparse

from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session
from starlette import status

from app.core.config import settings
from app.db.repositories import evaluation_tasks as repo
from app.schemas.evaluation_task import TaskCreateRequest, TaskCreateResponse
from app.services.evaluation_runner import run_evaluation_task
from app.utils.dataset_loader import load_dataset
from app.utils.storage import save_dataset_file

logger = logging.getLogger(__name__)


def _validate_agent_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_AGENT_URL", "message": "仅支持 HTTP 或 HTTPS URL"},
        )
    host = parsed.hostname or ""
    allowlist = settings.allowlist
    if "*" in allowlist:
        return
    if host not in allowlist:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "AGENT_URL_NOT_ALLOWED",
                "message": "该 API URL 未在白名单中允许访问",
            },
        )


def parse_headers(raw_headers: Optional[str]) -> Optional[dict]:
    if not raw_headers:
        return None
    try:
        parsed = json.loads(raw_headers)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "INVALID_AGENT_HEADERS",
                "message": "agent_api_headers 必须是合法的 JSON 对象",
            },
        ) from exc
    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "INVALID_AGENT_HEADERS",
                "message": "agent_api_headers 必须是 JSON 对象",
            },
        )
    return parsed


async def create_evaluation_task(
    db: Session,
    *,
    payload: TaskCreateRequest,
    dataset_file: UploadFile,
) -> TaskCreateResponse:
    agent_api_url = str(payload.agent_api_url)
    _validate_agent_url(agent_api_url)

    dataset_records, raw_file = await load_dataset(dataset_file)
    total_items = len(dataset_records)
    if total_items == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "DATASET_EMPTY", "message": "文件没有有效的问题数据"},
        )

    headers = dict(payload.agent_api_headers) if payload.agent_api_headers else {}
    if not headers and settings.default_agent_headers:
        headers = dict(settings.default_agent_headers)

    try:
        task = repo.create_task(
            db,
            task_name=payload.task_name.strip(),
            agent_api_url=agent_api_url.strip(),
            agent_api_headers=headers,
            agent_model=payload.agent_model.strip() if payload.agent_model else None,
            enable_correction=payload.enable_correction,
            runs_per_item=settings.runs_per_item,
            timeout_seconds=settings.timeout_seconds,
            use_stream=settings.use_stream,
            total_items=total_items,
        )

        items = repo.bulk_insert_items(db, task_id=task.id, items=dataset_records)
        for item in items:
            repo.create_initial_runs(db, item=item, runs_per_item=settings.runs_per_item)

        db.commit()
    except Exception:
        db.rollback()
        raise

    original_name = Path(dataset_file.filename or "dataset.csv").name
    save_dataset_file(task.id, original_name, raw_file)

    try:
        run_evaluation_task.delay(task.id)
    except Exception as exc:  # pragma: no cover - Celery backend might be unavailable
        logger.exception("failed to enqueue evaluation task %s: %s", task.id, exc)

    return TaskCreateResponse(
        task_id=task.id,
        status="PENDING",
        enable_correction=payload.enable_correction,
    )
