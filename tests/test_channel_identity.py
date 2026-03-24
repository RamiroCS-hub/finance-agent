from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.channel_identity import ChannelIdentityService
from app.services.user_service import build_identity_key, parse_identity_key


def test_parse_identity_key_defaults_to_whatsapp():
    assert parse_identity_key("5491112345678") == ("whatsapp", "5491112345678")


def test_parse_identity_key_understands_telegram_prefix():
    assert parse_identity_key("telegram:777001") == ("telegram", "777001")


def test_build_identity_key_keeps_whatsapp_legacy_shape():
    assert build_identity_key("whatsapp", "5491112345678") == "5491112345678"
    assert build_identity_key("telegram", "777001") == "telegram:777001"


@pytest.mark.asyncio
async def test_channel_identity_service_resolves_telegram_user():
    service = ChannelIdentityService()
    fake_user = SimpleNamespace(id=7, whatsapp_number=None, default_timezone="UTC", plan="PREMIUM")
    session = AsyncMock()

    with patch("app.services.channel_identity.async_session_maker") as mock_session_maker:
        mock_session_maker.return_value.__aenter__.return_value = session
        with patch(
            "app.services.channel_identity.get_or_create_user",
            new=AsyncMock(return_value=fake_user),
        ) as mock_get_or_create_user:
            ctx = await service.resolve_private_user(
                channel="telegram",
                external_user_id="777001",
                chat_id="777001",
                display_name="Ana",
            )

    mock_get_or_create_user.assert_awaited_once()
    assert ctx.user_id == 7
    assert ctx.channel == "telegram"
    assert ctx.external_user_id == "777001"
    assert ctx.identity_key == "telegram:777001"
    assert ctx.phone_number is None
