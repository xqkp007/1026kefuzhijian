from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import AnyHttpUrl, BaseModel, Field, field_validator

from app.db.models.evaluation_task import RunStatus, TaskStatus


class TaskCreateRequest(BaseModel):
    task_name: str = Field(..., min_length=1, max_length=64)
    agent_api_url: AnyHttpUrl
    agent_api_headers: Optional[Dict[str, Any]] = Field(default=None)
    agent_model: Optional[str] = Field(default=None, max_length=128)
    enable_correction: bool = Field(default=False)

    @field_validator("agent_model")
    @classmethod
    def _trim_model(cls, value: Optional[str]) -> Optional[str]:
        if value:
            return value.strip()
        return value


class TaskCreateResponse(BaseModel):
    task_id: str = Field(..., alias="task_id")
    status: Literal["PENDING"]
    enable_correction: bool


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total: int


class TaskListItem(BaseModel):
    task_id: str
    task_name: str
    status: Literal["PENDING", "RUNNING", "SUCCEEDED", "FAILED"]
    enable_correction: bool
    accuracy_rate: Optional[float] = None
    progress: Dict[str, int]
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None


class TaskListResponse(BaseModel):
    items: List[TaskListItem]
    pagination: PaginationMeta


class EvaluationRunSchema(BaseModel):
    run_index: int
    status: Literal[
        RunStatus.SUCCEEDED,
        RunStatus.FAILED,
        RunStatus.TIMEOUT,
        RunStatus.RETRYING,
    ]
    response_body: Optional[str]
    latency_ms: Optional[int]
    error_code: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    correction_status: str | None = None
    correction_result: Optional[bool] = None
    correction_reason: Optional[str] = None
    correction_error_message: Optional[str] = None
    correction_retries: Optional[int] = None


class EvaluationItemSchema(BaseModel):
    question_id: str
    question: str
    standard_answer: str
    system_prompt: Optional[str]
    user_context: Optional[str]
    is_passed: Optional[bool] = None
    failure_type: Optional[str] = None
    runs: List[EvaluationRunSchema]


class TaskResultResponse(BaseModel):
    task: Dict[str, Any]
    items: List[EvaluationItemSchema]
    pagination: PaginationMeta


class ExportFormat(str, Enum):
    CSV = "csv"
    XLSX = "xlsx"


class ExportQueryParams(BaseModel):
    format: ExportFormat = Field(default=ExportFormat.CSV)
    include_errors: bool = Field(default=True)
