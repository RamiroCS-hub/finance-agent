from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.telegram import send_text


@pytest.mark.asyncio
async def test_send_text_returns_message_id():
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"ok": True, "result": {"message_id": 42}}

    with patch("app.services.telegram.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=response)
        with patch("app.services.telegram.settings.TELEGRAM_BOT_TOKEN", "fake-token"):
            message_id = await send_text("777001", "Hola Telegram")

    assert message_id == "42"


@pytest.mark.asyncio
async def test_send_text_returns_none_on_error():
    response = MagicMock()
    response.status_code = 500
    response.text = "boom"

    with patch("app.services.telegram.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=response)
        with patch("app.services.telegram.settings.TELEGRAM_BOT_TOKEN", "fake-token"):
            message_id = await send_text("777001", "Hola Telegram")

    assert message_id is None
