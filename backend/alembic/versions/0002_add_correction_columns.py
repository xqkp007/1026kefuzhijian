"""Add correction toggle and metrics columns

Revision ID: 0002_add_correction_columns
Revises: 0001_create_evaluation_tables
Create Date: 2024-10-29 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0002_add_correction_columns"
down_revision = "0001_create_evaluation_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("evaluation_tasks", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "enable_correction",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(sa.Column("accuracy_rate", sa.Float(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "passed_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )

    # Remove server defaults after backfilling existing rows.
    with op.batch_alter_table("evaluation_tasks", schema=None) as batch_op:
        batch_op.alter_column("enable_correction", server_default=None)
        batch_op.alter_column("passed_count", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("evaluation_tasks", schema=None) as batch_op:
        batch_op.drop_column("passed_count")
        batch_op.drop_column("accuracy_rate")
        batch_op.drop_column("enable_correction")

