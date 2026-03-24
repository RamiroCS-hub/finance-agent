import pytest
import httpx
import hmac
import hashlib
import json
import logging
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.api import webhook
from app.config import settings
from app.services.plan_usage import QuotaDecision
from app.services.rate_limit import RateLimitDecision

client = TestClient(app)


def signed_headers(payload: dict, secret: str) -> dict[str, str]:
    body = json.dumps(payload).encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": f"sha256={digest}",
    }


def signed_post(payload: dict):
    return client.post(
        "/webhook",
        data=json.dumps(payload),
        headers=signed_headers(payload, settings.WHATSAPP_APP_SECRET),
    )

@pytest.fixture(autouse=True)
def mock_agent():
    mock = AsyncMock()
    mock.process = AsyncMock(return_value="Respuesta de prueba")
    mock.memory = MagicMock()
    mock.memory.store_wamid = MagicMock()
    mock.expense_store = MagicMock()
    mock.expense_store.append_expense = AsyncMock(
        return_value=MagicMock(id=5, spent_at=datetime.now(timezone.utc))
    )
    mock.group_expense_service = MagicMock()
    mock.group_expense_service.register_group_expense = AsyncMock(
        return_value={"success": True, "group_expense_id": 9}
    )
    webhook.init_dependencies(mock, rate_limiter=None)
    return mock

@pytest.fixture(autouse=True)
def mock_db_services():
    with patch("app.db.database.async_session_maker") as mock_session:
        session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = session_instance
        
        with patch("app.services.user_service.get_or_create_user", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = MagicMock(
                id=7,
                plan="PREMIUM",
                default_timezone="America/Argentina/Buenos_Aires",
            )
            with patch("app.api.webhook.check_media_allowed", new_callable=AsyncMock) as mock_check_media:
                with patch("app.services.group_service.ensure_group_member", new_callable=AsyncMock) as mock_group_member:
                    yield {
                        "session": mock_session,
                        "get_user": mock_get_user,
                        "check_media": mock_check_media,
                        "ensure_group_member": mock_group_member,
                    }


@pytest.fixture(autouse=True)
def reset_settings():
    settings.ALLOWED_PHONE_NUMBERS = []
    settings.WHATSAPP_APP_SECRET = "top-secret"
    settings.WHATSAPP_REQUIRE_SIGNATURE = True
    settings.WHATSAPP_ALLOW_UNSIGNED_DEV_WEBHOOKS = False
    settings.WHATSAPP_MAX_AUDIO_BYTES = 16 * 1024 * 1024
    settings.WHATSAPP_MAX_IMAGE_BYTES = 10 * 1024 * 1024
    settings.WHATSAPP_ALLOWED_AUDIO_MIME_TYPES = ["audio/ogg", "audio/mpeg"]
    settings.WHATSAPP_ALLOWED_IMAGE_MIME_TYPES = ["image/jpeg", "image/png"]
    settings.GROUP_BOT_MENTION = "@anotamelo"
    settings.WHATSAPP_RATE_LIMIT_ENABLED = False
    yield
    settings.ALLOWED_PHONE_NUMBERS = []
    settings.WHATSAPP_APP_SECRET = "top-secret"
    settings.WHATSAPP_REQUIRE_SIGNATURE = True
    settings.WHATSAPP_ALLOW_UNSIGNED_DEV_WEBHOOKS = False
    settings.WHATSAPP_MAX_AUDIO_BYTES = 16 * 1024 * 1024
    settings.WHATSAPP_MAX_IMAGE_BYTES = 10 * 1024 * 1024
    settings.WHATSAPP_ALLOWED_AUDIO_MIME_TYPES = ["audio/ogg", "audio/mpeg"]
    settings.WHATSAPP_ALLOWED_IMAGE_MIME_TYPES = ["image/jpeg", "image/png"]
    settings.GROUP_BOT_MENTION = "@anotamelo"
    settings.WHATSAPP_RATE_LIMIT_ENABLED = False

@pytest.mark.asyncio
async def test_webhook_audio_processing(mock_agent):
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "5491112345678",
                                    "id": "wamid_123",
                                    "type": "audio",
                                    "audio": {"id": "media_id_456", "mime_type": "audio/ogg"}
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }
    
    settings.ALLOWED_PHONE_NUMBERS = ["5491112345678"]
    
    with patch("app.api.webhook.whatsapp.send_text", new_callable=AsyncMock) as mock_send_text:
        with patch("app.api.webhook.whatsapp.get_media_metadata", new_callable=AsyncMock) as mock_get_media_metadata:
            mock_get_media_metadata.return_value = {
                "url": "https://lookaside.test/audio",
                "mime_type": "audio/ogg",
                "file_size": 1200,
            }
            with patch("app.api.webhook.whatsapp.download_media", new_callable=AsyncMock) as mock_download_media:
                mock_download_media.return_value = b"fake_audio_bytes"
                with patch("app.services.private_media.transcription.transcribe_audio", new_callable=AsyncMock) as mock_transcribe_audio:
                    mock_transcribe_audio.return_value = "Audio transcrito"
                    
                    response = signed_post(payload)
                    
                    assert response.status_code == 200
                    assert response.json() == {"status": "ok"}
                    
                    mock_send_text.assert_any_call("5491112345678", "Escuchando audio... 🎧")
                    mock_download_media.assert_called_once_with("media_id_456")
                    mock_transcribe_audio.assert_called_once_with(b"fake_audio_bytes")
                    
                    mock_agent.process.assert_called_once_with(
                        "5491112345678",
                        "Audio transcrito",
                        replied_to_id=None,
                        chat_type="private",
                        group_id=None,
                    )


@pytest.mark.asyncio
async def test_webhook_audio_free_quota_exhausted(mock_agent, mock_db_services):
    mock_db_services["get_user"].return_value = MagicMock(
        id=7,
        plan="FREE",
        default_timezone="UTC",
    )
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "5491112345678",
                                    "id": "wamid_123",
                                    "type": "audio",
                                    "audio": {"id": "media_id_456", "mime_type": "audio/ogg"},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    settings.ALLOWED_PHONE_NUMBERS = ["5491112345678"]

    with patch(
        "app.api.webhook.check_quota",
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
        with patch("app.api.webhook.whatsapp.send_text", new_callable=AsyncMock) as mock_send_text:
            with patch("app.api.webhook.whatsapp.download_media", new_callable=AsyncMock) as mock_download_media:
                with patch("app.api.webhook.whatsapp.get_media_metadata", new_callable=AsyncMock) as mock_get_media_metadata:
                    mock_get_media_metadata.return_value = {
                        "url": "https://lookaside.test/audio",
                        "mime_type": "audio/ogg",
                        "file_size": 1200,
                    }
                    response = signed_post(payload)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    mock_download_media.assert_not_awaited()
    mock_agent.process.assert_not_called()
    mock_send_text.assert_awaited_once_with(
        "5491112345678",
        "🚀 Tu plan FREE ya llegó al máximo de 5 audios por semana. Pasate a PREMIUM para seguir enviando audios sin límite.",
    )

@pytest.mark.asyncio
async def test_webhook_text_processing(mock_agent):
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "5491112345678",
                                    "id": "wamid_123",
                                    "type": "text",
                                    "text": {"body": "Hola"}
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }
    
    settings.ALLOWED_PHONE_NUMBERS = ["5491112345678"]
    
    with patch("app.api.webhook.whatsapp.send_text", new_callable=AsyncMock) as mock_send_text:
        mock_send_text.return_value = "wamid_456"
        response = signed_post(payload)
        
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        
        mock_agent.process.assert_called_once_with(
            "5491112345678",
            "Hola",
            replied_to_id=None,
            chat_type="private",
            group_id=None,
        )
        mock_send_text.assert_called_once_with("5491112345678", "Respuesta de prueba")
        mock_agent.memory.store_wamid.assert_called_once_with("5491112345678", "wamid_456", "Respuesta de prueba")

@pytest.mark.asyncio
async def test_webhook_group_chat_ignored(mock_agent):
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "5491112345678",
                                    "id": "wamid_123",
                                    "type": "text",
                                    "text": {"body": "Hola grupo"},
                                    "group_id": "987654321"
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }
    
    settings.ALLOWED_PHONE_NUMBERS = ["5491112345678"]
    
    with patch("app.api.webhook.whatsapp.send_text", new_callable=AsyncMock) as mock_send_text:
        response = signed_post(payload)
        
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        
        mock_agent.process.assert_not_called()
        mock_send_text.assert_not_called()

@pytest.mark.asyncio
async def test_webhook_group_chat_processed(mock_agent):
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "5491112345678",
                                    "id": "wamid_123",
                                    "type": "text",
                                    "text": {"body": "@anotamelo gasté 500"},
                                    "group_id": "987654321"
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }
    
    settings.ALLOWED_PHONE_NUMBERS = ["5491112345678"]
    
    with patch("app.api.webhook.whatsapp.send_text", new_callable=AsyncMock) as mock_send_text:
        mock_send_text.return_value = "wamid_456"
        response = signed_post(payload)
        
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        
        mock_agent.process.assert_called_once_with(
            "5491112345678",
            "gasté 500",
            replied_to_id=None,
            chat_type="group",
            group_id="987654321",
        )
        mock_send_text.assert_called_once_with("987654321", "Respuesta de prueba")
        mock_agent.memory.store_wamid.assert_called_once_with(
            "group:987654321",
            "wamid_456",
            "Respuesta de prueba",
        )


@pytest.mark.asyncio
async def test_webhook_image_ocr_success(mock_agent):
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "5491112345678",
                                    "id": "wamid_123",
                                    "type": "image",
                                    "image": {
                                        "id": "media_id_789",
                                        "mime_type": "image/jpeg",
                                    },
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    settings.ALLOWED_PHONE_NUMBERS = ["5491112345678"]

    with patch("app.api.webhook.whatsapp.send_text", new_callable=AsyncMock) as mock_send_text:
        mock_send_text.side_effect = [None, "wamid_ocr"]
        with patch("app.api.webhook.whatsapp.get_media_metadata", new_callable=AsyncMock) as mock_get_media_metadata:
            mock_get_media_metadata.return_value = {
                "url": "https://lookaside.test/image",
                "mime_type": "image/jpeg",
                "file_size": 2048,
            }
            with patch("app.api.webhook.whatsapp.download_media", new_callable=AsyncMock) as mock_download_media:
                mock_download_media.return_value = b"fake-image"
                with patch(
                    "app.services.private_media.receipt_ocr.extract_receipt_candidate",
                    new_callable=AsyncMock,
                ) as mock_extract:
                    mock_extract.return_value = {
                        "status": "high_confidence",
                        "amount": 1234.0,
                        "shop": "Coto",
                        "category": "Supermercado",
                        "detected_text": "TOTAL 1234 COTO",
                    }

                    response = signed_post(payload)

    assert response.status_code == 200
    mock_agent.process.assert_not_called()
    mock_agent.expense_store.append_expense.assert_awaited_once()
    stored_expense = mock_agent.expense_store.append_expense.await_args.args[1]
    assert stored_expense.shop == "Coto"
    assert stored_expense.description == "Coto"
    mock_send_text.assert_any_call("5491112345678", "Procesando ticket... 📸")
    mock_send_text.assert_any_call("5491112345678", "✅ Registré *$1234.0* en *Coto*")


@pytest.mark.asyncio
async def test_webhook_image_ocr_low_confidence(mock_agent):
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "5491112345678",
                                    "id": "wamid_123",
                                    "type": "image",
                                    "image": {"id": "media_id_789", "mime_type": "image/jpeg"},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    settings.ALLOWED_PHONE_NUMBERS = ["5491112345678"]

    with patch("app.api.webhook.whatsapp.send_text", new_callable=AsyncMock) as mock_send_text:
        with patch("app.api.webhook.whatsapp.get_media_metadata", new_callable=AsyncMock) as mock_get_media_metadata:
            mock_get_media_metadata.return_value = {
                "url": "https://lookaside.test/image",
                "mime_type": "image/jpeg",
                "file_size": 2048,
            }
            with patch("app.api.webhook.whatsapp.download_media", new_callable=AsyncMock) as mock_download_media:
                mock_download_media.return_value = b"fake-image"
                with patch(
                    "app.services.private_media.receipt_ocr.extract_receipt_candidate",
                    new_callable=AsyncMock,
                ) as mock_extract:
                    mock_extract.return_value = {
                        "status": "low_confidence",
                        "amount": None,
                        "shop": None,
                        "category": "Otros",
                    }
                    response = signed_post(payload)

    assert response.status_code == 200
    mock_agent.expense_store.append_expense.assert_not_called()
    mock_send_text.assert_any_call(
        "5491112345678",
        "No pude extraer datos confiables del ticket. Probá con una foto más clara o registralo por texto.",
    )


def test_webhook_rejects_invalid_signature(mock_agent):
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "5491112345678",
                                    "id": "wamid_123",
                                    "type": "text",
                                    "text": {"body": "Hola"}
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    settings.ALLOWED_PHONE_NUMBERS = ["5491112345678"]
    settings.WHATSAPP_APP_SECRET = "top-secret"

    response = client.post(
        "/webhook",
        data=json.dumps(payload),
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": "sha256=bad-signature",
        },
    )

    assert response.status_code == 401
    mock_agent.process.assert_not_called()


def test_webhook_accepts_valid_signature(mock_agent):
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "5491112345678",
                                    "id": "wamid_123",
                                    "type": "text",
                                    "text": {"body": "Hola"}
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    settings.ALLOWED_PHONE_NUMBERS = ["5491112345678"]

    with patch("app.api.webhook.whatsapp.send_text", new_callable=AsyncMock) as mock_send_text:
        mock_send_text.return_value = "wamid_456"
        response = signed_post(payload)

    assert response.status_code == 200
    mock_agent.process.assert_called_once()


def test_webhook_rejects_when_signature_required_but_secret_missing(mock_agent):
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "5491112345678",
                                    "id": "wamid_123",
                                    "type": "text",
                                    "text": {"body": "Hola"}
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    settings.ALLOWED_PHONE_NUMBERS = ["5491112345678"]
    settings.WHATSAPP_APP_SECRET = ""

    response = client.post("/webhook", json=payload)

    assert response.status_code == 503
    mock_agent.process.assert_not_called()


def test_webhook_accepts_unsigned_when_dev_bypass_enabled(mock_agent):
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "5491112345678",
                                    "id": "wamid_123",
                                    "type": "text",
                                    "text": {"body": "Hola"}
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    settings.ALLOWED_PHONE_NUMBERS = ["5491112345678"]
    settings.WHATSAPP_APP_SECRET = ""
    settings.WHATSAPP_ALLOW_UNSIGNED_DEV_WEBHOOKS = True

    with patch("app.api.webhook.whatsapp.send_text", new_callable=AsyncMock) as mock_send_text:
        mock_send_text.return_value = "wamid_456"
        response = client.post("/webhook", json=payload)

    assert response.status_code == 200
    mock_agent.process.assert_called_once()


def test_webhook_rate_limit_blocks_processing(mock_agent):
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "5491112345678",
                                    "id": "wamid_123",
                                    "type": "text",
                                    "text": {"body": "Hola"}
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    settings.ALLOWED_PHONE_NUMBERS = ["5491112345678"]
    settings.WHATSAPP_RATE_LIMIT_ENABLED = True
    rate_limiter = AsyncMock()
    rate_limiter.allow_message.return_value = RateLimitDecision(
        allowed=False,
        remaining=0,
        retry_after_seconds=27,
        should_notify=True,
    )
    webhook.init_dependencies(mock_agent, rate_limiter=rate_limiter)

    with patch("app.api.webhook.whatsapp.send_text", new_callable=AsyncMock) as mock_send_text:
        response = signed_post(payload)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    rate_limiter.allow_message.assert_awaited_once_with("5491112345678")
    mock_agent.process.assert_not_called()
    mock_send_text.assert_called_once_with(
        "5491112345678",
        "Estás mandando muchos mensajes muy rápido. Esperá 27s y probá de nuevo.",
    )


def test_webhook_rate_limit_fail_open(mock_agent):
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "5491112345678",
                                    "id": "wamid_123",
                                    "type": "text",
                                    "text": {"body": "Hola"}
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    settings.ALLOWED_PHONE_NUMBERS = ["5491112345678"]
    settings.WHATSAPP_RATE_LIMIT_ENABLED = True
    rate_limiter = AsyncMock()
    rate_limiter.allow_message.side_effect = RuntimeError("redis down")
    webhook.init_dependencies(mock_agent, rate_limiter=rate_limiter)

    with patch("app.api.webhook.whatsapp.send_text", new_callable=AsyncMock) as mock_send_text:
        mock_send_text.return_value = "wamid_456"
        response = signed_post(payload)

    assert response.status_code == 200
    rate_limiter.allow_message.assert_awaited_once_with("5491112345678")
    mock_agent.process.assert_called_once_with(
        "5491112345678",
        "Hola",
        replied_to_id=None,
        chat_type="private",
        group_id=None,
    )
    mock_send_text.assert_called_once_with("5491112345678", "Respuesta de prueba")


def test_webhook_discarded_group_message_does_not_consume_rate_limit(mock_agent):
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "5491112345678",
                                    "id": "wamid_123",
                                    "type": "text",
                                    "text": {"body": "Hola grupo"},
                                    "group_id": "987654321"
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    settings.ALLOWED_PHONE_NUMBERS = ["5491112345678"]
    settings.WHATSAPP_RATE_LIMIT_ENABLED = True
    rate_limiter = AsyncMock()
    webhook.init_dependencies(mock_agent, rate_limiter=rate_limiter)

    response = signed_post(payload)

    assert response.status_code == 200
    rate_limiter.allow_message.assert_not_called()
    mock_agent.process.assert_not_called()


def test_webhook_rejects_oversized_image_before_processing(mock_agent):
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "5491112345678",
                                    "id": "wamid_123",
                                    "type": "image",
                                    "image": {"id": "media_id_789", "mime_type": "image/jpeg"},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    settings.ALLOWED_PHONE_NUMBERS = ["5491112345678"]
    settings.WHATSAPP_MAX_IMAGE_BYTES = 100

    with patch("app.api.webhook.whatsapp.get_media_metadata", new_callable=AsyncMock) as mock_get_media_metadata:
        mock_get_media_metadata.return_value = {
            "url": "https://lookaside.test/image",
            "mime_type": "image/jpeg",
            "file_size": 101,
        }
        with patch("app.api.webhook.whatsapp.send_text", new_callable=AsyncMock) as mock_send_text:
            with patch("app.api.webhook.whatsapp.download_media", new_callable=AsyncMock) as mock_download_media:
                response = signed_post(payload)

    assert response.status_code == 200
    mock_agent.process.assert_not_called()
    mock_download_media.assert_not_called()
    mock_send_text.assert_called_once_with(
        "5491112345678",
        "El archivo es demasiado grande para procesarlo. Probá con uno más liviano.",
    )


def test_webhook_rejects_unsupported_audio_mime_before_processing(mock_agent):
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "5491112345678",
                                    "id": "wamid_123",
                                    "type": "audio",
                                    "audio": {"id": "media_id_456", "mime_type": "audio/wav"},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    settings.ALLOWED_PHONE_NUMBERS = ["5491112345678"]

    with patch("app.api.webhook.whatsapp.get_media_metadata", new_callable=AsyncMock) as mock_get_media_metadata:
        mock_get_media_metadata.return_value = {
            "url": "https://lookaside.test/audio",
            "mime_type": "audio/wav",
            "file_size": 1200,
        }
        with patch("app.api.webhook.whatsapp.send_text", new_callable=AsyncMock) as mock_send_text:
            with patch("app.api.webhook.whatsapp.download_media", new_callable=AsyncMock) as mock_download_media:
                response = signed_post(payload)

    assert response.status_code == 200
    mock_agent.process.assert_not_called()
    mock_download_media.assert_not_called()
    mock_send_text.assert_called_once_with(
        "5491112345678",
        "Ese tipo de archivo no está soportado para procesarlo automáticamente.",
    )


def test_webhook_logs_do_not_include_raw_message_text(mock_agent, caplog):
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "5491112345678",
                                    "id": "wamid_123",
                                    "type": "text",
                                    "text": {"body": "Hola mensaje confidencial"},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    settings.ALLOWED_PHONE_NUMBERS = ["5491112345678"]

    with patch("app.api.webhook.whatsapp.send_text", new_callable=AsyncMock) as mock_send_text:
        mock_send_text.return_value = "wamid_456"
        with caplog.at_level(logging.INFO):
            response = signed_post(payload)

    assert response.status_code == 200
    assert "Hola mensaje confidencial" not in caplog.text
    assert "5491112345678" not in caplog.text
    assert "...5678" in caplog.text
