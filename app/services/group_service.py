from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Group, GroupMember, User
from app.services.user_service import get_or_create_user


async def get_or_create_group(
    session: AsyncSession,
    whatsapp_group_id: str,
    name: str | None = None,
) -> Group:
    result = await session.execute(
        select(Group).where(Group.whatsapp_group_id == whatsapp_group_id)
    )
    group = result.scalars().first()

    if not group:
        group = Group(
            whatsapp_group_id=whatsapp_group_id,
            name=name or whatsapp_group_id,
        )
        session.add(group)
        await session.commit()
        await session.refresh(group)
        return group

    if name and group.name != name:
        group.name = name
        await session.commit()

    return group


async def ensure_group_member(
    session: AsyncSession,
    whatsapp_group_id: str,
    whatsapp_number: str,
    group_name: str | None = None,
    role: str = "member",
) -> tuple[Group, User, GroupMember]:
    user = await get_or_create_user(session, whatsapp_number)
    group = await get_or_create_group(session, whatsapp_group_id, name=group_name)

    result = await session.execute(
        select(GroupMember).where(
            GroupMember.user_id == user.id,
            GroupMember.group_id == group.id,
        )
    )
    membership = result.scalars().first()

    if not membership:
        membership = GroupMember(user_id=user.id, group_id=group.id, role=role)
        session.add(membership)
        await session.commit()
        await session.refresh(membership)

    return group, user, membership
