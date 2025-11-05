"""Add session_group column to evaluation_items

Revision ID: 0005_add_session_group
Revises: 0004_add_row_index
Create Date: 2025-11-05 00:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0005_add_session_group"
down_revision = "0004_add_row_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("evaluation_items", schema=None) as batch_op:
        batch_op.add_column(sa.Column("session_group", sa.String(length=128), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("evaluation_items", schema=None) as batch_op:
        batch_op.drop_column("session_group")

