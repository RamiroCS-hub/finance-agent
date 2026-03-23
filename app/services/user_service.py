from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import User, UserChannel
from app.services.timezones import infer_timezone_for_phone

CHANNEL_PREFIXES = {
    "telegram": "telegram:",
    "whatsapp": "whatsapp:",
}


def parse_identity_key(identity: str) -> tuple[str, str]:
    if identity.startswith(CHANNEL_PREFIXES["telegram"]):
        return "telegram", identity[len(CHANNEL_PREFIXES["telegram"]) :]
    if identity.startswith(CHANNEL_PREFIXES["whatsapp"]):
        return "whatsapp", identity[len(CHANNEL_PREFIXES["whatsapp"]) :]
    return "whatsapp", identity


def build_identity_key(channel: str, external_user_id: str) -> str:
    if channel == "whatsapp":
        return external_user_id
    prefix = CHANNEL_PREFIXES.get(channel, f"{channel}:")
    return f"{prefix}{external_user_id}"


async def get_user_channel(
    session: AsyncSession,
    channel: str,
    external_user_id: str,
) -> UserChannel | None:
    result = await session.execute(
        select(UserChannel).where(
            UserChannel.channel == channel,
            UserChannel.external_user_id == external_user_id,
        )
    )
    return result.scalar_one_or_none()


async def get_user_by_identity(session: AsyncSession, identity: str) -> User | None:
    channel, external_user_id = parse_identity_key(identity)
    if channel == "whatsapp":
        result = await session.execute(select(User).where(User.whatsapp_number == external_user_id))
        user = result.scalar_one_or_none()
        if user is not None:
            await ensure_user_channel(
                session,
                user,
                channel="whatsapp",
                external_user_id=external_user_id,
                chat_id=external_user_id,
            )
            return user

    result = await session.execute(
        select(User)
        .join(UserChannel, UserChannel.user_id == User.id)
        .where(
            UserChannel.channel == channel,
            UserChannel.external_user_id == external_user_id,
        )
    )
    return result.scalar_one_or_none()


async def ensure_user_channel(
    session: AsyncSession,
    user: User,
    channel: str,
    external_user_id: str,
    chat_id: str | None = None,
    display_name: str | None = None,
) -> UserChannel:
    channel_record = await get_user_channel(session, channel, external_user_id)
    if channel_record is None:
        channel_record = UserChannel(
            user_id=user.id,
            channel=channel,
            external_user_id=external_user_id,
            chat_id=chat_id or external_user_id,
            display_name=display_name,
        )
        session.add(channel_record)
        await session.flush()
        return channel_record

    changed = False
    if chat_id and channel_record.chat_id != chat_id:
        channel_record.chat_id = chat_id
        changed = True
    if display_name and channel_record.display_name != display_name:
        channel_record.display_name = display_name
        changed = True
    if changed:
        await session.flush()
    return channel_record


async def get_or_create_user(
    session: AsyncSession,
    identity: str,
    *,
    chat_id: str | None = None,
    display_name: str | None = None,
) -> User:
    """
    Get a user by canonical identity key, or create it if it doesn't exist.

    Supported forms:
    - WhatsApp legacy: `5491112345678`
    - Explicit WhatsApp: `whatsapp:5491112345678`
    - Telegram: `telegram:777001`
    """
    channel, external_user_id = parse_identity_key(identity)
    user = await get_user_by_identity(session, identity)
    if user is None:
        user = User(
            whatsapp_number=external_user_id if channel == "whatsapp" else None,
            default_timezone=_default_timezone(channel, external_user_id),
        )
        session.add(user)
        await session.flush()
    elif channel == "whatsapp" and not user.whatsapp_number:
        user.whatsapp_number = external_user_id

    if user.default_timezone is None:
        user.default_timezone = _default_timezone(channel, external_user_id)

    await ensure_user_channel(
        session,
        user,
        channel=channel,
        external_user_id=external_user_id,
        chat_id=chat_id or external_user_id,
        display_name=display_name,
    )
    await session.commit()
    await session.refresh(user)
    return user


def _default_timezone(channel: str, external_user_id: str) -> str:
    if channel == "whatsapp":
        return infer_timezone_for_phone(external_user_id)
    return settings.DEFAULT_USER_TIMEZONE
