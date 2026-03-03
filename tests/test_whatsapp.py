import pytest
import httpx
from unittest.mock import AsyncMock, patch
from app.services.whatsapp import download_media, GRAPH_API_URL
from app.config import settings

@pytest.mark.asyncio
async def test_download_media_success():
    mock_get_url_response = AsyncMock()
    mock_get_url_response.status_code = 200
    mock_get_url_response.json = lambda: {"url": "https://lookaside.fbsbx.com/whatsapp_business/attachments/?mid=123", "mime_type": "audio/ogg", "sha256": "hash", "file_size": 1234, "id": "media_id_123", "messaging_product": "whatsapp"}
    mock_get_url_response.raise_for_status = lambda: None

    mock_download_response = AsyncMock()
    mock_download_response.status_code = 200
    mock_download_response.content = b"fake_media_bytes"
    mock_download_response.raise_for_status = lambda: None

    # Side effect function to handle the two different GET requests
    async def mock_get(url, *args, **kwargs):
        if url == f"{GRAPH_API_URL}/media_id_123":
            return mock_get_url_response
        elif url == "https://lookaside.fbsbx.com/whatsapp_business/attachments/?mid=123":
            return mock_download_response
        else:
            raise ValueError(f"Unexpected URL called: {url}")

    with patch("httpx.AsyncClient.get", side_effect=mock_get) as mock_get_call:
        with patch("app.services.whatsapp.settings.WHATSAPP_TOKEN", "fake_token"):
            result = await download_media("media_id_123")
            
            assert result == b"fake_media_bytes"
            assert mock_get_call.call_count == 2
            
            # Verify first call
            call1_args, call1_kwargs = mock_get_call.call_args_list[0]
            assert call1_args[0] == f"{GRAPH_API_URL}/media_id_123"
            assert call1_kwargs["headers"]["Authorization"] == "Bearer fake_token"
            
            # Verify second call
            call2_args, call2_kwargs = mock_get_call.call_args_list[1]
            assert call2_args[0] == "https://lookaside.fbsbx.com/whatsapp_business/attachments/?mid=123"
            assert call2_kwargs["headers"]["Authorization"] == "Bearer fake_token"

@pytest.mark.asyncio
async def test_download_media_first_step_fails():
    mock_get_url_response = AsyncMock()
    mock_get_url_response.status_code = 404
    mock_get_url_response.text = "Not Found"
    
    # raise_for_status should raise an HTTPStatusError
    request = httpx.Request("GET", f"{GRAPH_API_URL}/media_id_123")
    def raise_err():
        raise httpx.HTTPStatusError(
            message="Not Found", request=request, response=mock_get_url_response
        )
    mock_get_url_response.raise_for_status = raise_err

    with patch("httpx.AsyncClient.get", return_value=mock_get_url_response):
        with patch("app.services.whatsapp.settings.WHATSAPP_TOKEN", "fake_token"):
            result = await download_media("media_id_123")
            assert result is None

@pytest.mark.asyncio
async def test_download_media_second_step_fails():
    mock_get_url_response = AsyncMock()
    mock_get_url_response.status_code = 200
    mock_get_url_response.json = lambda: {"url": "https://lookaside.fbsbx.com/whatsapp_business/attachments/?mid=123"}
    mock_get_url_response.raise_for_status = lambda: None

    mock_download_response = AsyncMock()
    mock_download_response.status_code = 500
    mock_download_response.text = "Internal Server Error"
    
    request = httpx.Request("GET", "https://lookaside.fbsbx.com/whatsapp_business/attachments/?mid=123")
    def raise_err():
        raise httpx.HTTPStatusError(
            message="Internal Server Error", request=request, response=mock_download_response
        )
    mock_download_response.raise_for_status = raise_err

    async def mock_get(url, *args, **kwargs):
        if url == f"{GRAPH_API_URL}/media_id_123":
            return mock_get_url_response
        elif url == "https://lookaside.fbsbx.com/whatsapp_business/attachments/?mid=123":
            return mock_download_response

    with patch("httpx.AsyncClient.get", side_effect=mock_get):
        with patch("app.services.whatsapp.settings.WHATSAPP_TOKEN", "fake_token"):
            result = await download_media("media_id_123")
            assert result is None
