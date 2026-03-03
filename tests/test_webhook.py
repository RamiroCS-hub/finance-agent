import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.api import webhook
from app.config import settings

client = TestClient(app)

@pytest.fixture(autouse=True)
def mock_agent():
    mock = AsyncMock()
    mock.process = AsyncMock(return_value="Respuesta de prueba")
    mock.memory = MagicMock()
    mock.memory.store_wamid = MagicMock()
    webhook.init_dependencies(mock)
    return mock

@pytest.fixture(autouse=True)
def mock_db_services():
    with patch("app.db.database.async_session_maker") as mock_session:
        session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = session_instance
        
        with patch("app.services.user_service.get_or_create_user", new_callable=AsyncMock) as mock_get_user:
            with patch("app.services.paywall.check_media_allowed", new_callable=AsyncMock) as mock_check_media:
                yield {
                    "session": mock_session,
                    "get_user": mock_get_user,
                    "check_media": mock_check_media
                }

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
        with patch("app.api.webhook.whatsapp.download_media", new_callable=AsyncMock) as mock_download_media:
            mock_download_media.return_value = b"fake_audio_bytes"
            with patch("app.api.webhook.transcription.transcribe_audio", new_callable=AsyncMock) as mock_transcribe_audio:
                mock_transcribe_audio.return_value = "Audio transcrito"
                
                response = client.post("/webhook", json=payload)
                
                assert response.status_code == 200
                assert response.json() == {"status": "ok"}
                
                mock_send_text.assert_any_call("5491112345678", "Escuchando audio... 🎧")
                mock_download_media.assert_called_once_with("media_id_456")
                mock_transcribe_audio.assert_called_once_with(b"fake_audio_bytes")
                
                mock_agent.process.assert_called_once_with("5491112345678", "Audio transcrito", replied_to_id=None)

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
        response = client.post("/webhook", json=payload)
        
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        
        mock_agent.process.assert_called_once_with("5491112345678", "Hola", replied_to_id=None)
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
        response = client.post("/webhook", json=payload)
        
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
                                    "text": {"body": "@Tesorero gasté 500"},
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
        response = client.post("/webhook", json=payload)
        
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        
        mock_agent.process.assert_called_once_with("5491112345678", "gasté 500", replied_to_id=None)
        mock_send_text.assert_called_once_with("5491112345678", "Respuesta de prueba")