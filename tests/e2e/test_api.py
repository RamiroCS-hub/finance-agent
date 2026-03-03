import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings

client = TestClient(app)

def test_verify_webhook_success():
    """Prueba la verificación GET de Meta para el webhook."""
    settings.WHATSAPP_VERIFY_TOKEN = "my-secret-token"
    
    response = client.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.challenge": "1158201444",
            "hub.verify_token": "my-secret-token"
        }
    )
    
    assert response.status_code == 200
    assert response.text == "1158201444"

def test_verify_webhook_failure():
    """Si el token es incorrecto, debe devolver 403."""
    settings.WHATSAPP_VERIFY_TOKEN = "my-secret-token"
    
    response = client.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.challenge": "1158201444",
            "hub.verify_token": "wrong-token"
        }
    )
    
    assert response.status_code == 403

def test_post_webhook_invalid_payload():
    """Un body mal formado o sin mensajes debe devolver status 'ok' para que Meta no reintente."""
    response = client.post("/webhook", json={"entry": []})
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
