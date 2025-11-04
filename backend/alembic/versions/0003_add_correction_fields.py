"""Add correction fields to runs and items

Revision ID: 0003_add_correction_fields
Revises: 0002_add_correction_columns
Create Date: 2024-10-29 10:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0003_add_correction_fields"
down_revision = "0002_add_correction_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("evaluation_items", schema=None) as batch_op:
        batch_op.add_column(sa.Column("is_passed", sa.Boolean(), nullable=True))

    with op.batch_alter_table("evaluation_runs", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("correction_status", sa.String(length=16), nullable=False, server_default="PENDING")
        )
        batch_op.add_column(sa.Column("correction_result", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("correction_reason", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("correction_error_message", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("correction_retries", sa.Integer(), nullable=False, server_default="0")
        )

    with op.batch_alter_table("evaluation_runs", schema=None) as batch_op:
        batch_op.alter_column("correction_status", server_default=None)
        batch_op.alter_column("correction_retries", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("evaluation_runs", schema=None) as batch_op:
        batch_op.drop_column("correction_retries")
        batch_op.drop_column("correction_error_message")
        batch_op.drop_column("correction_reason")
        batch_op.drop_column("correction_result")
        batch_op.drop_column("correction_status")

    with op.batch_alter_table("evaluation_items", schema=None) as batch_op:
        batch_op.drop_column("is_passed")
