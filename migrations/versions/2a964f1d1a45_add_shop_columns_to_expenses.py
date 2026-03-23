"""add shop columns to expenses

Revision ID: 2a964f1d1a45
Revises: 8f4d0f6e6cb7
Create Date: 2026-03-21 20:45:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2a964f1d1a45"
down_revision: Union[str, Sequence[str], None] = "8f4d0f6e6cb7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("expenses", sa.Column("shop", sa.String(), nullable=True))
    op.add_column("group_expenses", sa.Column("shop", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("group_expenses", "shop")
    op.drop_column("expenses", "shop")
