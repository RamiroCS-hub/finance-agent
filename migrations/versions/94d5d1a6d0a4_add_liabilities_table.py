"""add liabilities table

Revision ID: 94d5d1a6d0a4
Revises: 6bb2ccbe487d
Create Date: 2026-03-21 22:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "94d5d1a6d0a4"
down_revision: Union[str, Sequence[str], None] = "6bb2ccbe487d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "liabilities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False, server_default="ARS"),
        sa.Column("monthly_amount", sa.Float(), nullable=False),
        sa.Column("remaining_periods", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_liabilities_id"), "liabilities", ["id"], unique=False)
    op.create_index(op.f("ix_liabilities_user_id"), "liabilities", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_liabilities_user_id"), table_name="liabilities")
    op.drop_index(op.f("ix_liabilities_id"), table_name="liabilities")
    op.drop_table("liabilities")
