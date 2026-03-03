from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    whatsapp_number: Mapped[str] = mapped_column(String, unique=True, index=True)
    plan: Mapped[str] = mapped_column(String, default="FREE")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    group_memberships: Mapped[list["GroupMember"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    goals: Mapped[list["Goal"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    chat_configurations: Mapped[list["ChatConfiguration"]] = relationship(
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
