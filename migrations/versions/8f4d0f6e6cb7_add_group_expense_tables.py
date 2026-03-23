"""add group expense tables

Revision ID: 8f4d0f6e6cb7
Revises: c1b3f0a2d9f1
Create Date: 2026-03-21 20:15:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8f4d0f6e6cb7"
down_revision: Union[str, Sequence[str], None] = "c1b3f0a2d9f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "group_expenses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("payer_user_id", sa.Integer(), nullable=False),
        sa.Column("spent_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["payer_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_group_expenses_group_id"), "group_expenses", ["group_id"], unique=False)
    op.create_index(op.f("ix_group_expenses_id"), "group_expenses", ["id"], unique=False)
    op.create_index(
        op.f("ix_group_expenses_payer_user_id"), "group_expenses", ["payer_user_id"], unique=False
    )
    op.create_index(op.f("ix_group_expenses_spent_at"), "group_expenses", ["spent_at"], unique=False)

    op.create_table(
        "group_expense_shares",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("expense_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("share_amount", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["expense_id"], ["group_expenses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_group_expense_shares_expense_id"),
        "group_expense_shares",
        ["expense_id"],
        unique=False,
    )
    op.create_index(op.f("ix_group_expense_shares_id"), "group_expense_shares", ["id"], unique=False)
    op.create_index(
        op.f("ix_group_expense_shares_user_id"), "group_expense_shares", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_group_expense_shares_user_id"), table_name="group_expense_shares")
    op.drop_index(op.f("ix_group_expense_shares_id"), table_name="group_expense_shares")
    op.drop_index(op.f("ix_group_expense_shares_expense_id"), table_name="group_expense_shares")
    op.drop_table("group_expense_shares")
    op.drop_index(op.f("ix_group_expenses_spent_at"), table_name="group_expenses")
    op.drop_index(op.f("ix_group_expenses_payer_user_id"), table_name="group_expenses")
    op.drop_index(op.f("ix_group_expenses_id"), table_name="group_expenses")
    op.drop_index(op.f("ix_group_expenses_group_id"), table_name="group_expenses")
    op.drop_table("group_expenses")
