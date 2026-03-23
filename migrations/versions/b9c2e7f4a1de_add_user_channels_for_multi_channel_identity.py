"""Add user channels for multi-channel identity

Revision ID: b9c2e7f4a1de
Revises: 94d5d1a6d0a4
Create Date: 2026-03-23 22:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b9c2e7f4a1de"
down_revision: Union[str, Sequence[str], None] = "94d5d1a6d0a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("default_timezone", sa.String(), nullable=True))
    op.alter_column("users", "whatsapp_number", existing_type=sa.String(), nullable=True)

    op.create_table(
        "user_channels",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("external_user_id", sa.String(), nullable=False),
        sa.Column("chat_id", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("channel", "external_user_id", name="uq_user_channels_channel_external"),
    )
    op.create_index(op.f("ix_user_channels_id"), "user_channels", ["id"], unique=False)
    op.create_index(op.f("ix_user_channels_user_id"), "user_channels", ["user_id"], unique=False)
    op.create_index(op.f("ix_user_channels_channel"), "user_channels", ["channel"], unique=False)

    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            INSERT INTO user_channels (user_id, channel, external_user_id, chat_id)
            SELECT u.id, 'whatsapp', u.whatsapp_number, u.whatsapp_number
            FROM users u
            WHERE u.whatsapp_number IS NOT NULL
              AND NOT EXISTS (
                SELECT 1
                FROM user_channels uc
                WHERE uc.channel = 'whatsapp'
                  AND uc.external_user_id = u.whatsapp_number
              )
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE users
            SET whatsapp_number = uc.external_user_id
            FROM user_channels uc
            WHERE uc.user_id = users.id
              AND uc.channel = 'whatsapp'
              AND users.whatsapp_number IS NULL
            """
        )
    )
    bind.execute(sa.text("DELETE FROM users WHERE whatsapp_number IS NULL"))

    op.drop_index(op.f("ix_user_channels_channel"), table_name="user_channels")
    op.drop_index(op.f("ix_user_channels_user_id"), table_name="user_channels")
    op.drop_index(op.f("ix_user_channels_id"), table_name="user_channels")
    op.drop_table("user_channels")

    op.alter_column("users", "whatsapp_number", existing_type=sa.String(), nullable=False)
    op.drop_column("users", "default_timezone")
