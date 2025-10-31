"""Add row_index to evaluation_items for stable ordering

Revision ID: 0004_add_row_index
Revises: 0003_add_correction_fields
Create Date: 2025-10-29 00:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0004_add_row_index"
down_revision = "0003_add_correction_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) add the column as nullable first
    with op.batch_alter_table("evaluation_items", schema=None) as batch_op:
        batch_op.add_column(sa.Column("row_index", sa.Integer(), nullable=True))

    # 2) backfill using row_number per task
    op.execute(
        """
        WITH ranked AS (
            SELECT id, ROW_NUMBER() OVER (PARTITION BY task_id ORDER BY created_at, id) AS rn
            FROM evaluation_items
        )
        UPDATE evaluation_items ei
        SET row_index = r.rn
        FROM ranked r
        WHERE ei.id = r.id;
        """
    )

    # 3) set NOT NULL and add unique constraint
    with op.batch_alter_table("evaluation_items", schema=None) as batch_op:
        batch_op.alter_column("row_index", existing_type=sa.Integer(), nullable=False)
        batch_op.create_unique_constraint(
            "uq_evaluation_item_row", ["task_id", "row_index"]
        )


def downgrade() -> None:
    with op.batch_alter_table("evaluation_items", schema=None) as batch_op:
        batch_op.drop_constraint("uq_evaluation_item_row", type_="unique")
        batch_op.drop_column("row_index")
