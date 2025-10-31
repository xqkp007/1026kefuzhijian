import csv
import io
import re
from urllib.parse import quote
from datetime import datetime, timezone
from typing import Iterable, List
from zoneinfo import ZoneInfo

from fastapi.responses import StreamingResponse

from app.db.models.evaluation_task import EvaluationItem, EvaluationRun, EvaluationTask

BEIJING_TZ = ZoneInfo("Asia/Shanghai")


def _to_beijing_iso(dt: datetime | None, *, basic: bool = False) -> str:
    """Return formatted string in Beijing time."""
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    try:
        localized = dt.astimezone(BEIJING_TZ)
    except Exception:
        localized = dt
    if basic:
        return localized.strftime("%Y-%m-%d %H:%M:%S%z")
    return localized.isoformat()


def _sanitize_filename(name: str) -> str:
    base = (name or "").strip() or "evaluation"
    safe = re.sub(r'[<>:"/\\|?*]+', "_", base)
    safe = safe.strip("_") or "evaluation"
    return safe[:64]


def _ascii_fallback(name: str) -> str:
    """Return an ASCII-only fallback for HTTP header filename.

    Starlette encodes header values with latin-1. To avoid UnicodeEncodeError,
    the legacy `filename` parameter in Content-Disposition must contain
    ASCII-only characters. We keep the real name in `filename*`.
    """
    base = _sanitize_filename(name)
    # Remove non-ascii; collapse spaces to underscores; ensure non-empty
    ascii_name = (
        base.encode("ascii", "ignore").decode("ascii").strip() or "evaluation"
    )
    ascii_name = re.sub(r"\s+", "_", ascii_name)
    return ascii_name[:64]


def _build_headers(task: EvaluationTask, include_errors: bool) -> List[str]:
    headers = [
        "question_id",
        "question",
        "standard_answer",
        "_system_prompt",
        "_user_context",
        "is_passed",
    ]
    for idx in range(1, task.runs_per_item + 1):
        headers.append(f"run_{idx}_output")
        if include_errors:
            headers.extend(
                [
                    f"run_{idx}_status",
                    f"run_{idx}_latency_ms",
                    f"run_{idx}_error_code",
                    f"run_{idx}_correction_status",
                    f"run_{idx}_correction_result",
                    f"run_{idx}_correction_reason",
                    f"run_{idx}_correction_error",
                    f"run_{idx}_correction_retries",
                ]
            )
    headers.extend(["_created_at", "_completed_at"])
    return headers


def _run_lookup(item: EvaluationItem) -> dict[int, EvaluationRun]:
    return {run.run_index: run for run in item.runs}


def _bool_str(value: bool | None) -> str:
    if value is True:
        return "TRUE"
    if value is False:
        return "FALSE"
    return ""


def _build_row(
    task: EvaluationTask,
    item: EvaluationItem,
    include_errors: bool,
) -> List[str]:
    runs_index = _run_lookup(item)
    row: List[str] = [
        item.question_id,
        item.question,
        item.standard_answer,
        item.system_prompt or "",
        item.user_context or "",
        _bool_str(item.is_passed),
    ]
    for idx in range(1, task.runs_per_item + 1):
        run = runs_index.get(idx)
        row.append((run.response_body or "").replace("\r\n", "\n") if run else "")
        if include_errors:
            if run:
                row.extend(
                    [
                        run.status or "",
                        str(run.latency_ms) if run and run.latency_ms is not None else "",
                        run.error_code or "",
                        getattr(run, "correction_status", "") or "",
                        _bool_str(getattr(run, "correction_result", None)),
                        getattr(run, "correction_reason", "") or "",
                        getattr(run, "correction_error_message", "") or "",
                        str(getattr(run, "correction_retries", "") or ""),
                    ]
                )
            else:
                row.extend(["", "", "", "", "", "", "", ""])

    row.append(_to_beijing_iso(task.created_at))
    row.append(_to_beijing_iso(task.completed_at))
    return row


def _metadata_rows(task: EvaluationTask) -> List[List[str]]:
    rows: List[List[str]] = [
        ["任务名称", task.task_name],
        ["任务类型", "带矫正评测" if task.enable_correction else "纯评测任务"],
    ]
    if task.enable_correction:
        accuracy = f"{(task.accuracy_rate or 0):.1f}%"
        rows.append(["任务准确率", accuracy])
        rows.append(
            [
                "通过题数/总题数",
                f"{task.passed_count}/{task.total_items}" if task.total_items else "-",
            ]
        )
    else:
        rows.extend(
            [
                ["任务准确率", "-"],
                ["通过题数/总题数", "-"],
            ]
        )
    rows.append(["创建时间", _to_beijing_iso(task.created_at, basic=True)])
    return rows


def build_csv_stream_response(
    task: EvaluationTask,
    items: Iterable[EvaluationItem],
    *,
    include_errors: bool = True,
) -> StreamingResponse:
    headers = _build_headers(task, include_errors)

    def row_generator() -> Iterable[bytes]:
        yield "\ufeff".encode("utf-8")

        buffer = io.StringIO()
        writer = csv.writer(buffer)

        for row in _metadata_rows(task):
            writer.writerow(row)
            yield buffer.getvalue().encode("utf-8")
            buffer.seek(0)
            buffer.truncate(0)

        writer.writerow([])
        yield buffer.getvalue().encode("utf-8")
        buffer.seek(0)
        buffer.truncate(0)

        writer.writerow(headers)
        yield buffer.getvalue().encode("utf-8")
        buffer.seek(0)
        buffer.truncate(0)

        for item in items:
            writer.writerow(_build_row(task, item, include_errors))
            yield buffer.getvalue().encode("utf-8")
            buffer.seek(0)
            buffer.truncate(0)

    ascii_name = _ascii_fallback(task.task_name)
    filename = f"{ascii_name}_report.csv"
    # RFC 5987 encoding to preserve non-ASCII filename for modern browsers
    filename_star = quote(f"{task.task_name}_评测报告.csv", safe="")
    return StreamingResponse(
        row_generator(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{filename}"; '
                f"filename*=UTF-8''{filename_star}"
            )
        },
    )


def build_xlsx_response(
    task: EvaluationTask,
    items: Iterable[EvaluationItem],
    *,
    include_errors: bool = True,
):
    try:
        from openpyxl import Workbook
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("openpyxl is required for XLSX export") from exc

    wb = Workbook()
    ws = wb.active
    ws.title = "Evaluation Results"

    headers = _build_headers(task, include_errors)
    ws.append(headers)

    for item in items:
        ws.append(_build_row(task, item, include_errors))

    info_sheet = wb.create_sheet("Info")
    info_sheet.append(["属性", "值"])
    info_sheet.append(["任务名称", task.task_name])
    info_sheet.append(["任务状态", task.status])
    info_sheet.append(["运行次数", task.runs_per_item])
    info_sheet.append(["调用超时(s)", task.timeout_seconds])
    info_sheet.append(["任务创建时间", _to_beijing_iso(task.created_at)])
    info_sheet.append(["任务完成时间", _to_beijing_iso(task.completed_at)])

    stream = io.BytesIO()
    wb.save(stream)
    data = stream.getvalue()
    ascii_name = _ascii_fallback(task.task_name)
    filename = f"{ascii_name}_report.xlsx"
    filename_star = quote(f"{task.task_name}_report.xlsx", safe="")
    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{filename}"; '
                f"filename*=UTF-8''{filename_star}"
            )
        },
    )
