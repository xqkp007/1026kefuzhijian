from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Iterable, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models.evaluation_task import (
    EvaluationItem,
    EvaluationRun,
    EvaluationTask,
    RunStatus,
    TaskStatus,
    )


def try_claim_task(db: Session, task_id: str) -> Optional[EvaluationTask]:
    """Attempt to lock and mark a pending task as running.

    Returns the task instance if the claim succeeded, otherwise None.
    """
    stmt = (
        select(EvaluationTask)
        .where(EvaluationTask.id == task_id)
        .with_for_update(skip_locked=True)
    )
    task = db.scalar(stmt)
    if not task or task.status != TaskStatus.PENDING:
        return None
    now = datetime.now(timezone.utc)
    task.status = TaskStatus.RUNNING
    task.updated_at = now
    if not task.started_at:
        task.started_at = now
    db.add(task)
    db.flush()
    return task


def create_task(
    db: Session,
    *,
    task_name: str,
    agent_api_url: str,
    agent_api_headers: Optional[dict],
    agent_model: Optional[str],
    enable_correction: bool,
    runs_per_item: int,
    timeout_seconds: float,
    use_stream: bool,
    total_items: int,
) -> EvaluationTask:
    now = datetime.now(timezone.utc)
    task = EvaluationTask(
        task_name=task_name,
        agent_api_url=agent_api_url,
        agent_api_headers=agent_api_headers or {},
        agent_model=agent_model,
        enable_correction=enable_correction,
        status=TaskStatus.PENDING,
        total_items=total_items,
        progress_processed=0,
        runs_per_item=runs_per_item,
        timeout_seconds=timeout_seconds,
        use_stream=use_stream,
        created_at=now,
        updated_at=now,
    )
    db.add(task)
    db.flush()
    return task


def bulk_insert_items(
    db: Session,
    *,
    task_id: str,
    items: Iterable[dict],
) -> List[EvaluationItem]:
    created_items: List[EvaluationItem] = []
    # 使用严格递增的时间戳，保证与上传文件的顺序一致
    base = datetime.now(timezone.utc)
    for index, item in enumerate(items):
        created_at = base + timedelta(microseconds=index)
        evaluation_item = EvaluationItem(
            task_id=task_id,
            row_index=index + 1,
            question_id=item["question_id"],
            question=item["question"],
            standard_answer=item["standard_answer"],
            system_prompt=item.get("system_prompt"),
            user_context=item.get("user_context"),
            created_at=created_at,
        )
        db.add(evaluation_item)
        created_items.append(evaluation_item)
    db.flush()
    return created_items


def create_initial_runs(
    db: Session,
    *,
    item: EvaluationItem,
    runs_per_item: int,
) -> None:
    now = datetime.now(timezone.utc)
    for idx in range(1, runs_per_item + 1):
        db.add(
            EvaluationRun(
                item_id=item.id,
                run_index=idx,
                status=RunStatus.RETRYING,
                correction_status="PENDING",
                created_at=now,
                updated_at=now,
            )
        )
    db.flush()


def get_task(db: Session, task_id: str) -> Optional[EvaluationTask]:
    stmt = select(EvaluationTask).where(EvaluationTask.id == task_id)
    return db.scalar(stmt)


def list_items_for_task(db: Session, task_id: str) -> List[EvaluationItem]:
    stmt = (
        select(EvaluationItem)
        .where(EvaluationItem.task_id == task_id)
        .order_by(EvaluationItem.row_index, EvaluationItem.created_at)
        .options(selectinload(EvaluationItem.runs))
    )
    return list(db.scalars(stmt))


def mark_task_status(
    db: Session, task: EvaluationTask, status: str, *, set_started: bool = False
) -> None:
    now = datetime.now(timezone.utc)
    if set_started and not task.started_at:
        task.started_at = now
    task.status = status
    task.updated_at = now
    if status in {TaskStatus.SUCCEEDED, TaskStatus.FAILED}:
        task.completed_at = now
    db.add(task)


def increment_task_progress(
    db: Session, task: EvaluationTask, increment: int = 1
) -> None:
    task.progress_processed = min(task.progress_processed + increment, task.total_items)
    task.updated_at = datetime.now(timezone.utc)
    db.add(task)


def update_run_result(
    db: Session,
    run: EvaluationRun,
    *,
    status: str,
    response_body: Optional[str],
    latency_ms: Optional[int],
    error_code: Optional[str],
    error_message: Optional[str],
) -> None:
    now = datetime.now(timezone.utc)
    run.status = status
    run.response_body = response_body
    run.latency_ms = latency_ms
    run.error_code = error_code
    run.error_message = error_message
    run.updated_at = now
    db.add(run)


def update_run_correction(
    db: Session,
    run: EvaluationRun,
    *,
    status: str,
    result: Optional[bool],
    reason: Optional[str],
    error_message: Optional[str],
    retries: int,
) -> None:
    now = datetime.now(timezone.utc)
    run.correction_status = status
    run.correction_result = result
    run.correction_reason = reason
    run.correction_error_message = error_message
    run.correction_retries = retries
    run.updated_at = now
    db.add(run)


def update_item_pass_status(db: Session, item: EvaluationItem, is_passed: Optional[bool]) -> None:
    item.is_passed = is_passed
    db.add(item)


def calculate_accuracy(db: Session, task: EvaluationTask) -> None:
    total = db.scalar(
        select(func.count()).select_from(EvaluationItem).where(EvaluationItem.task_id == task.id)
    ) or 0
    passed = db.scalar(
        select(func.count())
        .select_from(EvaluationItem)
        .where(EvaluationItem.task_id == task.id, EvaluationItem.is_passed.is_(True))
    ) or 0
    accuracy = float(passed) / float(total) * 100 if total else 0.0
    task.passed_count = passed
    task.accuracy_rate = accuracy
    task.updated_at = datetime.now(timezone.utc)
    db.add(task)


def list_tasks_paginated(
    db: Session,
    *,
    page: int,
    page_size: int,
    status_filter: Optional[List[str]] = None,
    query: Optional[str] = None,
) -> tuple[List[EvaluationTask], int]:
    stmt = select(EvaluationTask)
    count_stmt = select(func.count()).select_from(EvaluationTask)

    if status_filter:
        stmt = stmt.where(EvaluationTask.status.in_(status_filter))
        count_stmt = count_stmt.where(EvaluationTask.status.in_(status_filter))
    if query:
        like = f"%{query}%"
        stmt = stmt.where(EvaluationTask.task_name.ilike(like))
        count_stmt = count_stmt.where(EvaluationTask.task_name.ilike(like))

    stmt = stmt.order_by(EvaluationTask.created_at.desc())

    total = db.scalar(count_stmt) or 0
    offset = (page - 1) * page_size
    items = list(db.scalars(stmt.offset(offset).limit(page_size)))
    return items, total


def list_task_results_paginated(
    db: Session,
    *,
    task_id: str,
    page: int,
    page_size: int,
    question_id: Optional[str] = None,
) -> tuple[List[EvaluationItem], int]:
    stmt = (
        select(EvaluationItem)
        .where(EvaluationItem.task_id == task_id)
        .order_by(EvaluationItem.created_at)
        .options(selectinload(EvaluationItem.runs))
    )
    count_stmt = select(func.count()).select_from(EvaluationItem).where(
        EvaluationItem.task_id == task_id
    )

    if question_id:
        stmt = stmt.where(EvaluationItem.question_id == question_id)
        count_stmt = count_stmt.where(EvaluationItem.question_id == question_id)

    total = db.scalar(count_stmt) or 0
    offset = (page - 1) * page_size
    items = list(db.scalars(stmt.offset(offset).limit(page_size)))
    return items, total
