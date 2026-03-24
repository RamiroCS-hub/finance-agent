from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api import telegram_webhook
from app.config import settings
from app.main import app
from app.services.channel_identity import ResolvedUserContext
from app.services.plan_usage import QuotaDecision

client = TestClient(app)


def telegram_headers(secret: str = "telegram-secret") -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-Telegram-Bot-Api-Secret-Token": secret,
    }


@pytest.fixture(autouse=True)
def reset_telegram_settings():
    settings.TELEGRAM_BOT_TOKEN = "telegram-token"
    settings.TELEGRAM_WEBHOOK_SECRET = "telegram-secret"
    settings.ALLOWED_TELEGRAM_CHAT_IDS = []
    settings.TELEGRAM_MAX_AUDIO_BYTES = 16 * 1024 * 1024
    settings.TELEGRAM_MAX_IMAGE_BYTES = 10 * 1024 * 1024
    settings.TELEGRAM_ALLOWED_AUDIO_MIME_TYPES = ["audio/ogg", "audio/mpeg"]
    settings.TELEGRAM_ALLOWED_IMAGE_MIME_TYPES = ["image/jpeg", "image/png"]
    yield
    settings.TELEGRAM_BOT_TOKEN = "telegram-token"
    settings.TELEGRAM_WEBHOOK_SECRET = "telegram-secret"
    settings.ALLOWED_TELEGRAM_CHAT_IDS = []
    settings.TELEGRAM_MAX_AUDIO_BYTES = 16 * 1024 * 1024
    settings.TELEGRAM_MAX_IMAGE_BYTES = 10 * 1024 * 1024
    settings.TELEGRAM_ALLOWED_AUDIO_MIME_TYPES = ["audio/ogg", "audio/mpeg"]
    settings.TELEGRAM_ALLOWED_IMAGE_MIME_TYPES = ["image/jpeg", "image/png"]


@pytest.fixture(autouse=True)
def mock_telegram_dependencies():
    mock_agent = AsyncMock()
    mock_agent.process = AsyncMock(return_value="Respuesta de prueba")
    mock_agent.memory = MagicMock()
    mock_agent.memory.store_message_ref = MagicMock()

    mock_dispatcher = AsyncMock()
    mock_dispatcher.send_text = AsyncMock(return_value="99")

    mock_identity_service = AsyncMock()
    mock_identity_service.resolve_private_user = AsyncMock(
        return_value=ResolvedUserContext(
            user_id=1,
            channel="telegram",
            external_user_id="777001",
            chat_id="777001",
            phone_number=None,
            timezone="UTC",
            plan="PREMIUM",
        )
    )

    mock_agent.expense_store = MagicMock()
    mock_agent.expense_store.append_expense = AsyncMock(
        return_value=MagicMock(id=5, spent_at=datetime.now(timezone.utc))
    )

    telegram_webhook.init_dependencies(
        mock_agent,
        dispatcher=mock_dispatcher,
        identity_service=mock_identity_service,
    )
    return {
        "agent": mock_agent,
        "dispatcher": mock_dispatcher,
        "identity_service": mock_identity_service,
    }


def test_telegram_webhook_private_text_success(mock_telegram_dependencies):
    payload = {
        "update_id": 1,
        "message": {
            "message_id": 10,
            "from": {"id": 777001, "first_name": "Ana"},
            "chat": {"id": 777001, "type": "private"},
            "text": "Hola",
        },
    }

    response = client.post("/telegram/webhook", json=payload, headers=telegram_headers())

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    mock_telegram_dependencies["identity_service"].resolve_private_user.assert_awaited_once()
    mock_telegram_dependencies["agent"].process.assert_awaited_once()
    mock_telegram_dependencies["dispatcher"].send_text.assert_awaited_once_with(
        "telegram", "777001", "Respuesta de prueba"
    )
    mock_telegram_dependencies["agent"].memory.store_message_ref.assert_called_once_with(
        "telegram:777001", "99", "Respuesta de prueba"
    )


def test_telegram_webhook_ignores_group_updates(mock_telegram_dependencies):
    payload = {
        "update_id": 1,
        "message": {
            "message_id": 10,
            "from": {"id": 777001, "first_name": "Ana"},
            "chat": {"id": -100123, "type": "group"},
            "text": "Hola grupo",
        },
    }

    response = client.post("/telegram/webhook", json=payload, headers=telegram_headers())

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    mock_telegram_dependencies["agent"].process.assert_not_called()


def test_telegram_webhook_processes_private_audio(mock_telegram_dependencies):
    payload = {
        "update_id": 2,
        "message": {
            "message_id": 11,
            "from": {"id": 777001, "first_name": "Ana"},
            "chat": {"id": 777001, "type": "private"},
            "voice": {
                "file_id": "voice-file-id",
                "duration": 4,
                "mime_type": "audio/ogg",
                "file_size": 1024,
            },
        },
    }

    with patch(
        "app.api.telegram_webhook.telegram.get_media_metadata",
        new=AsyncMock(
            return_value={
                "file_id": "voice-file-id",
                "file_path": "voice/file.ogg",
                "file_size": 1024,
                "mime_type": "audio/ogg",
            }
        ),
    ):
        with patch(
            "app.api.telegram_webhook.telegram.download_file",
            new=AsyncMock(return_value=b"voice-bytes"),
        ):
            with patch(
                "app.services.private_media.transcription.transcribe_audio",
                new=AsyncMock(return_value="Audio transcrito"),
            ):
                response = client.post("/telegram/webhook", json=payload, headers=telegram_headers())

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    mock_telegram_dependencies["identity_service"].resolve_private_user.assert_awaited_once()
    mock_telegram_dependencies["agent"].process.assert_awaited_once_with(
        mock_telegram_dependencies["identity_service"].resolve_private_user.return_value,
        "Audio transcrito",
        replied_to_id=None,
        chat_type="private",
        group_id=None,
    )
    assert mock_telegram_dependencies["dispatcher"].send_text.await_args_list[0].args == (
        "telegram",
        "777001",
        "Escuchando audio... 🎧",
    )
    assert mock_telegram_dependencies["dispatcher"].send_text.await_args_list[1].args == (
        "telegram",
        "777001",
        "Respuesta de prueba",
    )


def test_telegram_webhook_blocks_free_audio_when_quota_is_exhausted(mock_telegram_dependencies):
    mock_telegram_dependencies["identity_service"].resolve_private_user.return_value = ResolvedUserContext(
        user_id=1,
        channel="telegram",
        external_user_id="777001",
        chat_id="777001",
        phone_number=None,
        timezone="UTC",
        plan="FREE",
    )
    payload = {
        "update_id": 22,
        "message": {
            "message_id": 111,
            "from": {"id": 777001, "first_name": "Ana"},
            "chat": {"id": 777001, "type": "private"},
            "voice": {"file_id": "voice-file-id", "mime_type": "audio/ogg", "file_size": 1024},
        },
    }

    with patch(
        "app.api.telegram_webhook.check_quota",
        new=AsyncMock(
            return_value=QuotaDecision(
                allowed=False,
                limit=5,
                used=5,
                remaining=0,
                quota_key="audio_processing",
                period_kind="weekly",
            )
        ),
    ):
        with patch("app.api.telegram_webhook.telegram.get_media_metadata", new=AsyncMock()) as mock_metadata:
            response = client.post("/telegram/webhook", json=payload, headers=telegram_headers())

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    mock_metadata.assert_not_awaited()
    mock_telegram_dependencies["agent"].process.assert_not_called()
    mock_telegram_dependencies["dispatcher"].send_text.assert_awaited_once_with(
        "telegram",
        "777001",
        "🚀 Tu plan FREE ya llegó al máximo de 5 audios por semana. Pasate a PREMIUM para seguir enviando audios sin límite.",
    )


def test_telegram_webhook_processes_private_photo(mock_telegram_dependencies):
    payload = {
        "update_id": 3,
        "message": {
            "message_id": 12,
            "from": {"id": 777001, "first_name": "Ana"},
            "chat": {"id": 777001, "type": "private"},
            "photo": [
                {"file_id": "small", "file_size": 100},
                {"file_id": "large", "file_size": 500},
            ],
        },
    }

    with patch(
        "app.api.telegram_webhook.telegram.get_media_metadata",
        new=AsyncMock(
            return_value={
                "file_id": "large",
                "file_path": "photos/large.jpg",
                "file_size": 500,
                "mime_type": "image/jpeg",
            }
        ),
    ):
        with patch(
            "app.api.telegram_webhook.telegram.download_file",
            new=AsyncMock(return_value=b"image-bytes"),
        ):
            with patch(
                "app.services.private_media.receipt_ocr.extract_receipt_candidate",
                new=AsyncMock(
                    return_value={
                        "status": "high_confidence",
                        "amount": 1234.0,
                        "shop": "Coto",
                        "category": "Supermercado",
                        "detected_text": "TOTAL 1234 COTO",
                    }
                ),
            ):
                response = client.post("/telegram/webhook", json=payload, headers=telegram_headers())

    assert response.status_code == 200
    mock_telegram_dependencies["agent"].process.assert_not_called()
    mock_telegram_dependencies["agent"].expense_store.append_expense.assert_awaited_once()
    assert mock_telegram_dependencies["dispatcher"].send_text.await_args_list[0].args == (
        "telegram",
        "777001",
        "Procesando ticket... 📸",
    )
    assert mock_telegram_dependencies["dispatcher"].send_text.await_args_list[1].args == (
        "telegram",
        "777001",
        "✅ Registré *$1234.0* en *Coto*",
    )


def test_telegram_webhook_notifies_unsupported_private_document(mock_telegram_dependencies):
    payload = {
        "update_id": 4,
        "message": {
            "message_id": 13,
            "from": {"id": 777001, "first_name": "Ana"},
            "chat": {"id": 777001, "type": "private"},
            "document": {"file_id": "doc-id", "file_name": "invoice.pdf"},
        },
    }

    response = client.post("/telegram/webhook", json=payload, headers=telegram_headers())

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    mock_telegram_dependencies["agent"].process.assert_not_called()
    mock_telegram_dependencies["identity_service"].resolve_private_user.assert_not_awaited()
    mock_telegram_dependencies["dispatcher"].send_text.assert_awaited_once_with(
        "telegram",
        "777001",
        "En Telegram ya puedo procesar texto, audios e imagenes. Todavia no puedo analizar videos, documentos ni stickers por este canal.",
    )


def test_telegram_webhook_rejects_oversized_audio(mock_telegram_dependencies):
    payload = {
        "update_id": 5,
        "message": {
            "message_id": 14,
            "from": {"id": 777001, "first_name": "Ana"},
            "chat": {"id": 777001, "type": "private"},
            "voice": {"file_id": "voice-file-id", "mime_type": "audio/ogg", "file_size": 1024},
        },
    }

    settings.TELEGRAM_MAX_AUDIO_BYTES = 100

    with patch(
        "app.api.telegram_webhook.telegram.get_media_metadata",
        new=AsyncMock(
            return_value={
                "file_id": "voice-file-id",
                "file_path": "voice/file.ogg",
                "file_size": 101,
                "mime_type": "audio/ogg",
            }
        ),
    ):
        response = client.post("/telegram/webhook", json=payload, headers=telegram_headers())

    assert response.status_code == 200
    mock_telegram_dependencies["agent"].process.assert_not_called()
    mock_telegram_dependencies["dispatcher"].send_text.assert_awaited_once_with(
        "telegram",
        "777001",
        "El archivo es demasiado grande para procesarlo. Probá con uno más liviano.",
    )


def test_telegram_webhook_rejects_invalid_secret(mock_telegram_dependencies):
    payload = {
        "update_id": 1,
        "message": {
            "message_id": 10,
            "from": {"id": 777001, "first_name": "Ana"},
            "chat": {"id": 777001, "type": "private"},
            "text": "Hola",
        },
    }

    response = client.post("/telegram/webhook", json=payload, headers=telegram_headers("bad-secret"))

    assert response.status_code == 401


def test_telegram_webhook_requires_configuration(mock_telegram_dependencies):
    settings.TELEGRAM_BOT_TOKEN = ""

    payload = {
        "update_id": 1,
        "message": {
            "message_id": 10,
            "from": {"id": 777001, "first_name": "Ana"},
            "chat": {"id": 777001, "type": "private"},
            "text": "Hola",
        },
    }

    response = client.post("/telegram/webhook", json=payload, headers=telegram_headers())

    assert response.status_code == 503


def test_telegram_webhook_deduplicates_update_id(mock_telegram_dependencies):
    payload = {
        "update_id": 12345,
        "message": {
            "message_id": 10,
            "from": {"id": 777001, "first_name": "Ana"},
            "chat": {"id": 777001, "type": "private"},
            "text": "Hola",
        },
    }

    first = client.post("/telegram/webhook", json=payload, headers=telegram_headers())
    second = client.post("/telegram/webhook", json=payload, headers=telegram_headers())

    assert first.status_code == 200
    assert second.status_code == 200
    assert mock_telegram_dependencies["agent"].process.await_count == 1
