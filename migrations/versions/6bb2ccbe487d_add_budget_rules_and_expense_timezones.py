"""add budget rules and expense timezones

Revision ID: 6bb2ccbe487d
Revises: 2a964f1d1a45
Create Date: 2026-03-21 21:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6bb2ccbe487d"
down_revision: Union[str, Sequence[str], None] = "2a964f1d1a45"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("expenses", sa.Column("source_timezone", sa.String(), nullable=True))
    op.add_column("group_expenses", sa.Column("source_timezone", sa.String(), nullable=True))

    op.create_table(
        "budget_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("period", sa.String(), nullable=False),
        sa.Column("limit_amount", sa.Float(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_budget_rules_id"), "budget_rules", ["id"], unique=False)
    op.create_index(op.f("ix_budget_rules_user_id"), "budget_rules", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_budget_rules_user_id"), table_name="budget_rules")
    op.drop_index(op.f("ix_budget_rules_id"), table_name="budget_rules")
    op.drop_table("budget_rules")
    op.drop_column("group_expenses", "source_timezone")
    op.drop_column("expenses", "source_timezone")
