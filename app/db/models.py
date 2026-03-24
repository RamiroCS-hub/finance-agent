from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    whatsapp_number: Mapped[Optional[str]] = mapped_column(
        String, unique=True, index=True, nullable=True
    )
    plan: Mapped[str] = mapped_column(String, default="FREE")
    default_timezone: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    channels: Mapped[list["UserChannel"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    group_memberships: Mapped[list["GroupMember"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    goals: Mapped[list["Goal"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    chat_configurations: Mapped[list["ChatConfiguration"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    expenses: Mapped[list["Expense"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    liabilities: Mapped[list["Liability"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    paid_group_expenses: Mapped[list["GroupExpense"]] = relationship(
        back_populates="payer", cascade="all, delete-orphan"
    )
    group_expense_shares: Mapped[list["GroupExpenseShare"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    budget_rules: Mapped[list["BudgetRule"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    plan_usage_events: Mapped[list["PlanUsageEvent"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    whatsapp_group_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    members: Mapped[list["GroupMember"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )
    goals: Mapped[list["Goal"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )
    chat_configurations: Mapped[list["ChatConfiguration"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )
    expenses: Mapped[list["GroupExpense"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )


class GroupMember(Base):
    __tablename__ = "group_members"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String, default="member")
    joined_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    user: Mapped["User"] = relationship(back_populates="group_memberships")
    group: Mapped["Group"] = relationship(back_populates="members")


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    group_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), nullable=True, index=True
    )
    target_amount: Mapped[float] = mapped_column(default=0.0)
    current_amount: Mapped[float] = mapped_column(default=0.0)
    status: Mapped[str] = mapped_column(String, default="active")

    # Relationships
    user: Mapped[Optional["User"]] = relationship(back_populates="goals")
    group: Mapped[Optional["Group"]] = relationship(back_populates="goals")


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    spent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
        server_default=func.now(),
    )
    amount: Mapped[float] = mapped_column(default=0.0)
    currency: Mapped[str] = mapped_column(String, default="ARS")
    shop: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source_timezone: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    description: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String, default="General")
    calculation: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    raw_message: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String, default="agent")
    original_amount: Mapped[Optional[float]] = mapped_column(nullable=True)
    original_currency: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="expenses")


class GroupExpense(Base):
    __tablename__ = "group_expenses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    payer_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    spent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
        server_default=func.now(),
    )
    amount: Mapped[float] = mapped_column(default=0.0)
    currency: Mapped[str] = mapped_column(String, default="ARS")
    shop: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source_timezone: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    description: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String, default="General")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    group: Mapped["Group"] = relationship(back_populates="expenses")
    payer: Mapped["User"] = relationship(back_populates="paid_group_expenses")
    shares: Mapped[list["GroupExpenseShare"]] = relationship(
        back_populates="expense", cascade="all, delete-orphan"
    )


class GroupExpenseShare(Base):
    __tablename__ = "group_expense_shares"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    expense_id: Mapped[int] = mapped_column(
        ForeignKey("group_expenses.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    share_amount: Mapped[float] = mapped_column(default=0.0)

    expense: Mapped["GroupExpense"] = relationship(back_populates="shares")
    user: Mapped["User"] = relationship(back_populates="group_expense_shares")


class BudgetRule(Base):
    __tablename__ = "budget_rules"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String)
    period: Mapped[str] = mapped_column(String, default="monthly")
    limit_amount: Mapped[float] = mapped_column(default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="budget_rules")


class Liability(Base):
    __tablename__ = "liabilities"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String, default="installment")
    description: Mapped[str] = mapped_column(String)
    currency: Mapped[str] = mapped_column(String, default="ARS")
    monthly_amount: Mapped[float] = mapped_column(default=0.0)
    remaining_periods: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(String, default="active")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="liabilities")


class ChatConfiguration(Base):
    __tablename__ = "chat_configurations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    group_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), nullable=True, index=True
    )
    custom_prompt: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Relationships
    user: Mapped[Optional["User"]] = relationship(back_populates="chat_configurations")
    group: Mapped[Optional["Group"]] = relationship(back_populates="chat_configurations")


class UserChannel(Base):
    __tablename__ = "user_channels"
    __table_args__ = (
        UniqueConstraint("channel", "external_user_id", name="uq_user_channels_channel_external"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String, index=True)
    external_user_id: Mapped[str] = mapped_column(String)
    chat_id: Mapped[str] = mapped_column(String)
    display_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="channels")


class PlanUsageEvent(Base):
    __tablename__ = "plan_usage_events"
    __table_args__ = (
        UniqueConstraint("user_id", "quota_key", "source_ref", name="uq_plan_usage_user_quota_source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    quota_key: Mapped[str] = mapped_column(String, index=True)
    period_kind: Mapped[str] = mapped_column(String)
    source_ref: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    consumed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
        server_default=func.now(),
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="plan_usage_events")
