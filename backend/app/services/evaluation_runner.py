from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Tuple, Optional

import httpx
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.core.config import settings
from app.db.models.evaluation_task import RunStatus, TaskStatus
from app.db.repositories import evaluation_tasks as repo
from app.db.session import SessionLocal
from app.services.zhipu_runner import ZhipuConfigurationError, ZhipuRunner
from app.services.correction_service import (
    CorrectionConfigurationError,
    CorrectionOutcome,
    CorrectionService,
)

logger = logging.getLogger(__name__)


def _prepare_payload(item: Any, task) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "doc_list": [],
        "image_url": "",
        "query": item.question,
        "session_id": "",
        "stream": task.use_stream,
    }

    # 追加默认扩展字段（例如 appId、bizType 等）
    if settings.default_agent_extra_fields:
        for k, v in settings.default_agent_extra_fields.items():
            payload.setdefault(k, v)

    # 清理 None/空串，stream 保留
    return {k: v for k, v in payload.items() if v not in (None, "") or k == "stream"}


def _parse_stream_response(response: httpx.Response) -> Tuple[str, str | None, str]:
    content_parts: list[str] = []
    raw_segments: list[str] = []
    error_message = None
    for raw_line in response.iter_lines():
        if not raw_line:
            continue
        if isinstance(raw_line, bytes):
            line = raw_line.decode("utf-8", errors="ignore")
        else:
            line = str(raw_line)
        stripped = line.strip()
        if not stripped:
            continue
        raw_segments.append(stripped)
        if stripped.startswith("data:"):
            stripped = stripped[5:].strip()
        try:
            event_payload = json.loads(stripped)
        except json.JSONDecodeError:
            logger.debug("Unable to decode stream segment: %s", stripped)
            continue

        event = event_payload.get("event")
        data = event_payload.get("data", {})
        if event in {"llm_chunk", "reasoning_chunk"}:
            delta = (
                data.get("choices", [{}])[0]
                .get("delta", {})
                .get("content")
            )
            if delta:
                content_parts.append(delta)
        elif event == "reasoning_start":
            content_parts.append("<think>\n")
        elif event == "reasoning_end":
            content_parts.append("</think>\n")
        elif event == "node_finished":
            output = data.get("output")
            if isinstance(output, dict):
                if output.get("output"):
                    content_parts.append(f"{output['output']}\n")
                if output.get("content"):
                    content_parts.append(f"{output['content']}\n")
            elif isinstance(output, str):
                content_parts.append(f"{output}\n")
        elif event == "llm_error":
            error_message = data.get("error_message") or "Agent returned llm_error event"

    return "".join(content_parts).strip(), error_message, "\n".join(raw_segments)


def _parse_json_response(raw_text: str) -> Tuple[str, str | None]:
    try:
        data = json.loads(raw_text, strict=False)
    except json.JSONDecodeError:
        return "", "Agent response is not valid JSON"

    output_lines: list[str] = []
    error_message = None

    if isinstance(data, dict):
        code = data.get("code")
        success_codes = {None, 0, "0", 200, "200"}
        if code not in success_codes:
            msg = data.get("msg") or data.get("message")
            if msg:
                error_message = str(msg)
        outer_data = data.get("data", {}) if isinstance(data.get("data"), dict) else {}
        text = outer_data.get("text")
        if isinstance(text, list):
            output_lines.extend([str(item) for item in text])
        elif isinstance(text, str):
            output_lines.append(text)
        inner_data = outer_data.get("data", {}) if isinstance(outer_data.get("data"), dict) else {}
        outputs_to_consider = [
            outer_data.get("output"),
            inner_data.get("output"),
            inner_data.get("content"),
        ]
        for val in outputs_to_consider:
            if isinstance(val, list):
                output_lines.extend([str(item) for item in val if item])
            elif isinstance(val, str):
                output_lines.append(val)

    return "\n".join(line for line in output_lines if line).strip(), error_message


def _perform_request(
    client: httpx.Client,
    task,
    item,
    run,
    *,
    headers: Dict[str, str],
) -> Tuple[str, str | None, str | None]:
    payload = _prepare_payload(item, task)
    if "Content-Type" not in headers:
        headers["Content-Type"] = "application/json"

    context = (
        f"task={task.id} item={item.question_id} run={getattr(run, 'run_index', 'n/a')}"
    )

    if task.use_stream:
        with client.stream("POST", task.agent_api_url, json=payload, headers=headers) as response:
            if response.status_code != 200:
                body = response.text
                logger.info(
                    "Agent response (stream, error) [%s] status=%s body=%s",
                    context,
                    response.status_code,
                    body,
                )
                return "", f"HTTP_{response.status_code}", body
            content, err, raw_dump = _parse_stream_response(response)
            logger.info("Agent response (stream) [%s]: %s", context, raw_dump or "<empty>")
            if err:
                return "", "AGENT_ERROR", err
            return content or "", None, None

    response = client.post(
        task.agent_api_url,
        json=payload,
        headers=headers,
    )
    raw_text = response.text
    logger.info(
        "Agent response (json) [%s] status=%s body=%s",
        context,
        response.status_code,
        raw_text or "<empty>",
    )
    if response.status_code != 200:
        return "", f"HTTP_{response.status_code}", raw_text
    content, err = _parse_json_response(raw_text)
    if err:
        return "", "AGENT_ERROR", err
    return content, None, None


def _execute_single_run(
    client: httpx.Client,
    task,
    item,
    run,
) -> Tuple[str, str | None, str | None, int]:
    attempts = 0
    max_attempts = settings.request_max_retries + 1
    last_error_code: str | None = None
    last_error_message: str | None = None

    while attempts < max_attempts:
        attempts += 1
        started = time.perf_counter()
        try:
            content, error_code, error_message = _perform_request(
                client, task, item, run, headers={**(task.agent_api_headers or {})}
            )
            latency_ms = int((time.perf_counter() - started) * 1000)
            if error_code or error_message:
                last_error_code = error_code or "AGENT_ERROR"
                last_error_message = error_message
            else:
                logger.info(
                    "Agent parsed content [%s]: %s",
                    f"task={task.id} item={item.question_id} run={run.run_index}",
                    (content[:200] + "..." if len(content) > 200 else content),
                )
                return content, None, None, latency_ms
        except httpx.TimeoutException:
            last_error_code = "TIMEOUT"
            last_error_message = f"Agent request timed out after {settings.timeout_seconds}s"
        except httpx.TransportError as exc:
            last_error_code = "NETWORK_ERROR"
            last_error_message = str(exc)

        if attempts < max_attempts:
            time.sleep(1)  # 指数退避可后续扩展

    latency_ms = int((time.perf_counter() - started) * 1000)
    return "", last_error_code, last_error_message, latency_ms


def _run_corrections_for_item(
    db: Session,
    *,
    task,
    item,
    correction_service: Optional[CorrectionService],
) -> None:
    runs = sorted(item.runs, key=lambda r: r.run_index)
    if not correction_service:
        for run in runs:
            repo.update_run_correction(
                db,
                run,
                status="SKIPPED",
                result=None,
                reason=None,
                error_message="Correction service unavailable",
                retries=0,
            )
        repo.update_item_pass_status(db, item, False)
        logger.warning("Task %s question %s: correction skipped (service unavailable)", task.id, item.question_id)
        return

    all_correct = True
    for run in runs:
        if run.status != RunStatus.SUCCEEDED or not run.response_body:
            repo.update_run_correction(
                db,
                run,
                status="FAILED",
                result=False,
                reason=None,
                error_message=run.error_message or "Agent run failed",
                retries=0,
            )
            all_correct = False
            continue

        outcome: CorrectionOutcome = correction_service.evaluate(
            question=item.question,
            standard_answer=item.standard_answer,
            agent_output=run.response_body,
        )
        repo.update_run_correction(
            db,
            run,
            status=outcome.status,
            result=outcome.is_correct,
            reason=outcome.reason,
            error_message=outcome.error_message,
            retries=outcome.retries,
        )
        if outcome.status != "SUCCESS" or not outcome.is_correct:
            all_correct = False

    repo.update_item_pass_status(db, item, all_correct)


def _process_task(db: Session, task_id: str) -> None:
    task = repo.try_claim_task(db, task_id)
    if not task:
        logger.info("Task %s already claimed or finished, skipping execution", task_id)
        return
    db.commit()

    use_zhipu = False
    zhipu_runner: ZhipuRunner | None = None
    agent_model = (task.agent_model or "").lower()
    agent_api_url = (task.agent_api_url or "").lower()
    if agent_model.startswith("zhipu") or agent_api_url.startswith("zhipu://"):
        use_zhipu = True
        try:
            zhipu_runner = ZhipuRunner()
        except ZhipuConfigurationError as exc:
            logger.error("初始化智谱客户端失败：%s", exc)
            repo.mark_task_status(db, task, TaskStatus.FAILED)
            db.commit()
            return

    timeout = httpx.Timeout(settings.timeout_seconds, read=settings.timeout_seconds)
    client: httpx.Client | None = None
    if not use_zhipu:
        client = httpx.Client(timeout=timeout)

    correction_service: CorrectionService | None = None
    if task.enable_correction:
        try:
            correction_service = CorrectionService()
        except CorrectionConfigurationError as exc:
            logger.error("矫正服务初始化失败：%s", exc)
            correction_service = None

    try:
        items = repo.list_items_for_task(db, task_id)
        total_items = len(items)
        for item_index, item in enumerate(items, start=1):
            logger.info(
                "Task %s: start question %s/%s (%s)",
                task.id,
                item_index,
                total_items,
                item.question_id,
            )
            runs = sorted(item.runs, key=lambda r: r.run_index)
            pending_runs = [run for run in runs if run.status == RunStatus.RETRYING]
            if not pending_runs:
                logger.info(
                    "Task %s question %s already completed, skip re-processing",
                    task.id,
                    item.question_id,
                )
                continue
            for run in pending_runs:
                logger.info(
                    "Task %s question %s run #%s started",
                    task.id,
                    item.question_id,
                    run.run_index,
                )
                if use_zhipu and zhipu_runner is not None:
                    content, error_code, error_message, latency_ms = zhipu_runner.execute(
                        task, item, run
                    )
                else:
                    content, error_code, error_message, latency_ms = _execute_single_run(
                        client, task, item, run
                    )
                if error_code:
                    status = RunStatus.TIMEOUT if error_code == "TIMEOUT" else RunStatus.FAILED
                else:
                    status = RunStatus.SUCCEEDED
                repo.update_run_result(
                    db,
                    run,
                    status=status,
                    response_body=content or None,
                    latency_ms=latency_ms,
                    error_code=error_code,
                    error_message=error_message,
                )
                logger.info(
                    "Task %s question %s run #%s finished status=%s latency=%sms error_code=%s",
                    task.id,
                    item.question_id,
                    run.run_index,
                    status,
                    latency_ms,
                    error_code or "",
                )
                db.commit()

            if task.enable_correction:
                _run_corrections_for_item(
                    db,
                    task=task,
                    item=item,
                    correction_service=correction_service,
                )
                db.commit()

            repo.increment_task_progress(db, task)
            db.commit()
            logger.info(
                "Task %s: question %s finished, progress=%s/%s",
                task.id,
                item.question_id,
                task.progress_processed,
                task.total_items,
            )

        repo.mark_task_status(db, task, TaskStatus.SUCCEEDED)
        db.commit()
        if task.enable_correction:
            repo.calculate_accuracy(db, task)
            db.commit()
    except Exception:
        db.rollback()
        repo.mark_task_status(db, task, TaskStatus.FAILED)
        db.commit()
        logger.exception("Failed to process evaluation task %s", task_id)
    finally:
        if client:
            client.close()


@celery_app.task(name="app.services.evaluation_runner.run_evaluation_task")
def run_evaluation_task(task_id: str) -> None:
    db = SessionLocal()
    try:
        _process_task(db, task_id)
    finally:
        db.close()
