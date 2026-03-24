from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.telegram import download_file, get_file, get_media_metadata, send_text


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


@pytest.mark.asyncio
async def test_get_file_returns_result():
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "ok": True,
        "result": {"file_id": "abc123", "file_path": "voice/file.ogg", "file_size": 321},
    }

    with patch("app.services.telegram.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=response)
        with patch("app.services.telegram.settings.TELEGRAM_BOT_TOKEN", "fake-token"):
            result = await get_file("abc123")

    assert result["file_path"] == "voice/file.ogg"


@pytest.mark.asyncio
async def test_get_media_metadata_for_voice_uses_get_file():
    with patch(
        "app.services.telegram.get_file",
        new=AsyncMock(return_value={"file_path": "voice/file.ogg", "file_size": 987}),
    ):
        metadata = await get_media_metadata(
            {
                "voice": {
                    "file_id": "voice-id",
                    "mime_type": "audio/ogg",
                    "file_size": 123,
                }
            }
        )

    assert metadata == {
        "file_id": "voice-id",
        "file_path": "voice/file.ogg",
        "file_size": 987,
        "mime_type": "audio/ogg",
    }


@pytest.mark.asyncio
async def test_get_media_metadata_for_photo_chooses_largest_variant():
    with patch(
        "app.services.telegram.get_file",
        new=AsyncMock(return_value={"file_path": "photos/large.jpg", "file_size": 555}),
    ):
        metadata = await get_media_metadata(
            {
                "photo": [
                    {"file_id": "small", "file_size": 100},
                    {"file_id": "large", "file_size": 400},
                ]
            }
        )

    assert metadata == {
        "file_id": "large",
        "file_path": "photos/large.jpg",
        "file_size": 555,
        "mime_type": "image/jpeg",
    }


@pytest.mark.asyncio
async def test_download_file_returns_bytes():
    response = MagicMock()
    response.status_code = 200
    response.content = b"telegram-bytes"

    with patch("app.services.telegram.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=response)
        with patch("app.services.telegram.settings.TELEGRAM_BOT_TOKEN", "fake-token"):
            result = await download_file("photos/large.jpg")

    assert result == b"telegram-bytes"
