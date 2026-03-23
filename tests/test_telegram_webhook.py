from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api import telegram_webhook
from app.config import settings
from app.main import app
from app.services.channel_identity import ResolvedUserContext

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
    yield
    settings.TELEGRAM_BOT_TOKEN = "telegram-token"
    settings.TELEGRAM_WEBHOOK_SECRET = "telegram-secret"
    settings.ALLOWED_TELEGRAM_CHAT_IDS = []


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
        )
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
