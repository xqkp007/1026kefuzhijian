from datetime import datetime, timezone
from typing import List, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session
from starlette import status

from app.api.dependencies import get_db_session
from app.db.models.evaluation_task import TaskStatus
from app.db.repositories import evaluation_tasks as repo
from app.schemas.evaluation_task import (
    PaginationMeta,
    TaskResultResponse,
    TaskCreateRequest,
    TaskCreateResponse,
    TaskListItem,
    TaskListResponse,
    EvaluationItemSchema,
    EvaluationRunSchema,
    ExportQueryParams,
)
from app.services.task_service import create_evaluation_task, parse_headers
from app.services.statistics import CorrectionAggregator
from app.utils.exporter import build_csv_stream_response, build_xlsx_response

router = APIRouter(prefix="/evaluation-tasks", tags=["evaluation-tasks"])

BEIJING_TZ = ZoneInfo("Asia/Shanghai")


def _to_beijing(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    try:
        return dt.astimezone(BEIJING_TZ)
    except Exception:
        return dt


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=TaskCreateResponse,
)
async def create_task(
    task_name: str = Form(...),
    agent_api_url: str = Form(...),
    dataset_file: UploadFile = File(...),
    agent_api_headers: str | None = Form(default=None),
    agent_model: str | None = Form(default=None),
    enable_correction: bool = Form(default=False),
    db: Session = Depends(get_db_session),
) -> TaskCreateResponse:
    payload = TaskCreateRequest(
        task_name=task_name,
        agent_api_url=agent_api_url,
        agent_api_headers=parse_headers(agent_api_headers),
        agent_model=agent_model,
        enable_correction=enable_correction,
    )
    return await create_evaluation_task(db, payload=payload, dataset_file=dataset_file)


@router.get("", response_model=TaskListResponse)
def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[List[str]] = Query(None, alias="status"),
    query: Optional[str] = Query(None),
    db: Session = Depends(get_db_session),
) -> TaskListResponse:
    if status_filter:
        invalid = set(status_filter) - TaskStatus.ALL
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "INVALID_STATUS_FILTER",
                    "message": f"status 参数包含非法值: {', '.join(invalid)}",
                },
            )

    tasks, total = repo.list_tasks_paginated(
        db,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
        query=query,
    )

    items: List[TaskListItem] = []
    for task in tasks:
        duration_seconds: float | None = None
        if task.completed_at:
            duration_seconds = (task.completed_at - task.created_at).total_seconds()
        items.append(
            TaskListItem(
                task_id=task.id,
                task_name=task.task_name,
                status=task.status,
                enable_correction=task.enable_correction,
                accuracy_rate=task.accuracy_rate,
                progress={"processed": task.progress_processed, "total": task.total_items},
                created_at=_to_beijing(task.created_at),
                updated_at=_to_beijing(task.updated_at),
                completed_at=_to_beijing(task.completed_at),
                duration_seconds=duration_seconds,
            )
        )

    pagination = PaginationMeta(page=page, page_size=page_size, total=total)
    return TaskListResponse(items=items, pagination=pagination)


@router.get("/{task_id}/results", response_model=TaskResultResponse)
def get_task_results(
    task_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    question_id: str | None = Query(None),
    db: Session = Depends(get_db_session),
) -> TaskResultResponse:
    task = repo.get_task(db, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "TASK_NOT_FOUND", "message": "任务不存在"},
        )
    if task.status != TaskStatus.SUCCEEDED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "TASK_NOT_FINISHED", "message": "任务尚未完成"},
        )

    items, total = repo.list_task_results_paginated(
        db,
        task_id=task_id,
        page=page,
        page_size=page_size,
        question_id=question_id,
    )

    aggregator = None
    failure_type_map: dict[str, str] = {}
    if task.enable_correction:
        aggregator = CorrectionAggregator()
        all_items = repo.list_items_for_task(db, task_id)
        for full_item in all_items:
            aggregator.observe_item(full_item)
        failure_type_map = dict(aggregator.item_failure_types)

    item_models: List[EvaluationItemSchema] = []
    for item in items:
        runs = sorted(item.runs, key=lambda r: r.run_index)
        run_models = [
            EvaluationRunSchema(
                run_index=run.run_index,
                status=run.status,
                response_body=run.response_body,
                latency_ms=run.latency_ms,
                error_code=run.error_code,
                error_message=run.error_message,
                created_at=_to_beijing(run.created_at),
                correction_status=getattr(run, "correction_status", None),
                correction_result=getattr(run, "correction_result", None),
                correction_reason=getattr(run, "correction_reason", None),
                correction_error_message=getattr(run, "correction_error_message", None),
                correction_retries=getattr(run, "correction_retries", None),
            )
            for run in runs
        ]
        item_models.append(
            EvaluationItemSchema(
                question_id=item.question_id,
                question=item.question,
                standard_answer=item.standard_answer,
                system_prompt=item.system_prompt,
                user_context=item.user_context,
                session_group=getattr(item, "session_group", None),
                is_passed=getattr(item, "is_passed", None),
                failure_type=failure_type_map.get(item.question_id),
                runs=run_models,
            )
        )

    pagination = PaginationMeta(page=page, page_size=page_size, total=total)
    task_info = {
        "task_id": task.id,
        "task_name": task.task_name,
        "status": task.status,
        "runs_per_item": task.runs_per_item,
        "timeout_seconds": task.timeout_seconds,
        "enable_correction": task.enable_correction,
        "accuracy_rate": task.accuracy_rate,
        "passed_count": task.passed_count,
        "failed_count": (task.total_items - task.passed_count) if task.total_items else 0,
        "total_items": task.total_items,
        "completed_at": _to_beijing(task.completed_at),
        "created_at": _to_beijing(task.created_at),
        "updated_at": _to_beijing(task.updated_at),
    }

    if aggregator:
        stats = aggregator.to_stats()
        task_info["passed_count"] = stats.passed
        task_info["partial_error_count"] = stats.partial_error_count
        task_info["correction_failed_count"] = stats.correction_failed_count
        task_info["failed_count"] = stats.failed_total
        task_info["total_items"] = stats.total_items
        task_info["accuracy_rate"] = stats.accuracy_rate

    return TaskResultResponse(task=task_info, items=item_models, pagination=pagination)


@router.get("/{task_id}/export")
def export_task_results(
    task_id: str,
    format: str = Query("csv"),
    include_errors: bool = Query(True),
    db: Session = Depends(get_db_session),
):
    task = repo.get_task(db, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "TASK_NOT_FOUND", "message": "任务不存在"},
        )
    if task.status != TaskStatus.SUCCEEDED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "TASK_NOT_FINISHED", "message": "任务尚未完成"},
        )

    params = ExportQueryParams(format=format, include_errors=include_errors)
    items = repo.list_items_for_task(db, task_id)

    if params.format == "csv":
        return build_csv_stream_response(task, items, include_errors=params.include_errors)
    if params.format == "xlsx":
        return build_xlsx_response(task, items, include_errors=params.include_errors)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"code": "UNSUPPORTED_EXPORT_FORMAT", "message": "仅支持 csv 或 xlsx"},
    )
