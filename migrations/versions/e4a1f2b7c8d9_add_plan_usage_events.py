"""Add plan usage events

Revision ID: e4a1f2b7c8d9
Revises: b9c2e7f4a1de
Create Date: 2026-03-23 23:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e4a1f2b7c8d9"
down_revision: Union[str, Sequence[str], None] = "b9c2e7f4a1de"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "plan_usage_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("quota_key", sa.String(), nullable=False),
        sa.Column("period_kind", sa.String(), nullable=False),
        sa.Column("source_ref", sa.String(), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "quota_key", "source_ref", name="uq_plan_usage_user_quota_source"),
    )
    op.create_index(op.f("ix_plan_usage_events_id"), "plan_usage_events", ["id"], unique=False)
    op.create_index(op.f("ix_plan_usage_events_user_id"), "plan_usage_events", ["user_id"], unique=False)
    op.create_index(op.f("ix_plan_usage_events_quota_key"), "plan_usage_events", ["quota_key"], unique=False)
    op.create_index(op.f("ix_plan_usage_events_consumed_at"), "plan_usage_events", ["consumed_at"], unique=False)
    op.create_index(
        "ix_plan_usage_events_user_quota_consumed_at",
        "plan_usage_events",
        ["user_id", "quota_key", "consumed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_plan_usage_events_user_quota_consumed_at", table_name="plan_usage_events")
    op.drop_index(op.f("ix_plan_usage_events_consumed_at"), table_name="plan_usage_events")
    op.drop_index(op.f("ix_plan_usage_events_quota_key"), table_name="plan_usage_events")
    op.drop_index(op.f("ix_plan_usage_events_user_id"), table_name="plan_usage_events")
    op.drop_index(op.f("ix_plan_usage_events_id"), table_name="plan_usage_events")
    op.drop_table("plan_usage_events")
