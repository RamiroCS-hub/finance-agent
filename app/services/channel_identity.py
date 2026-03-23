from __future__ import annotations

from dataclasses import dataclass

from app.config import settings
from app.db.database import async_session_maker
from app.services.user_service import build_identity_key, get_or_create_user, parse_identity_key


@dataclass
class ResolvedUserContext:
    user_id: int
    channel: str
    external_user_id: str
    chat_id: str
    phone_number: str | None
    timezone: str

    @property
    def identity_key(self) -> str:
        return build_identity_key(self.channel, self.external_user_id)


class ChannelIdentityService:
    async def resolve_private_user(
        self,
        channel: str,
        external_user_id: str,
        chat_id: str,
        display_name: str | None = None,
    ) -> ResolvedUserContext:
        identity_key = build_identity_key(channel, external_user_id)
        async with async_session_maker() as session:
            user = await get_or_create_user(
                session,
                identity_key,
                chat_id=chat_id,
                display_name=display_name,
            )
            resolved_channel, resolved_external_user_id = parse_identity_key(identity_key)
            return ResolvedUserContext(
                user_id=user.id,
                channel=resolved_channel,
                external_user_id=resolved_external_user_id,
                chat_id=chat_id,
                phone_number=user.whatsapp_number,
                timezone=user.default_timezone or settings.DEFAULT_USER_TIMEZONE,
            )
