import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, relationship

from app.db.session import Base


class TaskStatus:
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"

    ALL = {PENDING, RUNNING, SUCCEEDED, FAILED}


class RunStatus:
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    RETRYING = "RETRYING"

    ALL = {SUCCEEDED, FAILED, TIMEOUT, RETRYING}


def generate_uuid() -> str:
    return str(uuid.uuid4())


class EvaluationTask(Base):
    __tablename__ = "evaluation_tasks"

    id: Mapped[str] = Column(String(36), primary_key=True, default=generate_uuid, unique=True)
    task_name: Mapped[str] = Column(String(128), nullable=False)
    agent_api_url: Mapped[str] = Column(Text, nullable=False)
    agent_api_headers: Mapped[dict] = Column(JSON, nullable=True)
    agent_model: Mapped[str] = Column(String(128), nullable=True)

    enable_correction: Mapped[bool] = Column(Boolean, nullable=False, default=False)
    accuracy_rate: Mapped[float | None] = Column(Float, nullable=True)
    passed_count: Mapped[int] = Column(Integer, nullable=False, default=0)

    status: Mapped[str] = Column(String(16), nullable=False, default=TaskStatus.PENDING)
    total_items: Mapped[int] = Column(Integer, nullable=False, default=0)
    progress_processed: Mapped[int] = Column(Integer, nullable=False, default=0)

    runs_per_item: Mapped[int] = Column(Integer, nullable=False, default=5)
    timeout_seconds: Mapped[float] = Column(Float, nullable=False, default=30.0)
    use_stream: Mapped[bool] = Column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = Column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    started_at: Mapped[datetime | None] = Column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = Column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = Column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    items: Mapped[list["EvaluationItem"]] = relationship(
        "EvaluationItem",
        back_populates="task",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class EvaluationItem(Base):
    __tablename__ = "evaluation_items"

    id: Mapped[str] = Column(String(36), primary_key=True, default=generate_uuid, unique=True)
    task_id: Mapped[str] = Column(
        String(36), ForeignKey("evaluation_tasks.id", ondelete="CASCADE"), nullable=False
    )
    # 上传数据集中的行号（从1开始），用于稳定排序
    row_index: Mapped[int] = Column(Integer, nullable=False, default=1)
    question_id: Mapped[str] = Column(String(128), nullable=False)
    question: Mapped[str] = Column(Text, nullable=False)
    standard_answer: Mapped[str] = Column(Text, nullable=False)
    system_prompt: Mapped[str | None] = Column(Text, nullable=True)
    user_context: Mapped[str | None] = Column(Text, nullable=True)
    is_passed: Mapped[bool | None] = Column(Boolean, nullable=True)

    created_at: Mapped[datetime] = Column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    task: Mapped["EvaluationTask"] = relationship("EvaluationTask", back_populates="items")
    runs: Mapped[list["EvaluationRun"]] = relationship(
        "EvaluationRun",
        back_populates="item",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="EvaluationRun.run_index",
    )

    __table_args__ = (
        UniqueConstraint("task_id", "question_id", name="uq_evaluation_item_question"),
        UniqueConstraint("task_id", "row_index", name="uq_evaluation_item_row"),
    )


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[str] = Column(String(36), primary_key=True, default=generate_uuid, unique=True)
    item_id: Mapped[str] = Column(
        String(36),
        ForeignKey("evaluation_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    run_index: Mapped[int] = Column(Integer, nullable=False)
    status: Mapped[str] = Column(String(16), nullable=False, default=RunStatus.RETRYING)
    response_body: Mapped[str | None] = Column(Text, nullable=True)
    latency_ms: Mapped[int | None] = Column(Integer, nullable=True)
    error_code: Mapped[str | None] = Column(String(32), nullable=True)
    error_message: Mapped[str | None] = Column(Text, nullable=True)
    correction_status: Mapped[str] = Column(String(16), nullable=False, default="PENDING")
    correction_result: Mapped[bool | None] = Column(Boolean, nullable=True)
    correction_reason: Mapped[str | None] = Column(Text, nullable=True)
    correction_error_message: Mapped[str | None] = Column(Text, nullable=True)
    correction_retries: Mapped[int] = Column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = Column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    item: Mapped["EvaluationItem"] = relationship("EvaluationItem", back_populates="runs")

    __table_args__ = (
        UniqueConstraint("item_id", "run_index", name="uq_evaluation_run"),
    )
