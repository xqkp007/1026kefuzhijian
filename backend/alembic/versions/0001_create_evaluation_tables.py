"""create evaluation tables

Revision ID: 0001_create_evaluation_tables
Revises:
Create Date: 2024-10-26 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_create_evaluation_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evaluation_tasks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("task_name", sa.String(length=128), nullable=False),
        sa.Column("agent_api_url", sa.Text(), nullable=False),
        sa.Column("agent_api_headers", sa.JSON(), nullable=True),
        sa.Column("agent_model", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, default="PENDING"),
        sa.Column("total_items", sa.Integer(), nullable=False, default=0),
        sa.Column("progress_processed", sa.Integer(), nullable=False, default=0),
        sa.Column("runs_per_item", sa.Integer(), nullable=False, default=5),
        sa.Column("timeout_seconds", sa.Float(), nullable=False, default=30.0),
        sa.Column("use_stream", sa.Boolean(), nullable=False, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "evaluation_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("question_id", sa.String(length=128), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("standard_answer", sa.Text(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("user_context", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["evaluation_tasks.id"],
            name="fk_evaluation_items_task_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "task_id", "question_id", name="uq_evaluation_item_question"
        ),
    )

    op.create_table(
        "evaluation_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("item_id", sa.String(length=36), nullable=False),
        sa.Column("run_index", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, default="RETRYING"),
        sa.Column("response_body", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=32), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["evaluation_items.id"],
            name="fk_evaluation_runs_item_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("item_id", "run_index", name="uq_evaluation_run"),
    )


def downgrade() -> None:
    op.drop_table("evaluation_runs")
    op.drop_table("evaluation_items")
    op.drop_table("evaluation_tasks")
