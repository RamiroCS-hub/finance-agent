"""Tests para upload_media y send_document de WhatsApp."""
from __future__ import annotations
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.whatsapp import upload_media, send_document


@pytest.mark.asyncio
async def test_upload_media_returns_media_id():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"id": "media-abc-123"}

    with patch("app.services.whatsapp.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        result = await upload_media(b"%PDF content", "application/pdf", "reporte.pdf")

    assert result == "media-abc-123"


@pytest.mark.asyncio
async def test_upload_media_returns_none_on_error():
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request"

    with patch("app.services.whatsapp.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        result = await upload_media(b"data", "application/pdf", "f.pdf")

    assert result is None


@pytest.mark.asyncio
async def test_upload_media_returns_none_on_exception():
    with patch("app.services.whatsapp.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(side_effect=Exception("network"))
        result = await upload_media(b"data", "application/pdf", "f.pdf")

    assert result is None


@pytest.mark.asyncio
async def test_send_document_returns_wamid():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"messages": [{"id": "wamid.DOC123"}]}

    with patch("app.services.whatsapp.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        result = await send_document("5491112345678", "media-abc-123", "reporte.pdf", caption="Reporte Marzo")

    assert result == "wamid.DOC123"


@pytest.mark.asyncio
async def test_send_document_payload_contains_document_type():
    """Verifica que el payload enviado tenga type=document."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"messages": [{"id": "wamid.X"}]}

    captured = {}

    async def capture_post(url, **kwargs):
        captured["json"] = kwargs.get("json", {})
        return mock_response

    with patch("app.services.whatsapp.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = capture_post
        await send_document("5491112345678", "mid123", "report.pdf")

    assert captured["json"]["type"] == "document"
    assert captured["json"]["document"]["id"] == "mid123"
    assert captured["json"]["document"]["filename"] == "report.pdf"


@pytest.mark.asyncio
async def test_send_document_returns_none_on_error():
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Server Error"

    with patch("app.services.whatsapp.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        result = await send_document("5491112345678", "mid", "f.pdf")

    assert result is None
