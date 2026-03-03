import pytest
import httpx
from unittest.mock import AsyncMock, patch
from app.services.transcription import transcribe_audio

@pytest.mark.asyncio
async def test_transcribe_audio_success():
    # Simulate a successful response from Groq API
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = lambda: {"text": "Hola, este es un mensaje de prueba."}
    mock_response.raise_for_status = lambda: None

    audio_bytes = b"fake_audio_data_ogg"

    # Patch httpx.AsyncClient.post
    with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
        # We need to ensure settings.GROQ_API_KEY is used
        with patch("app.services.transcription.settings.GROQ_API_KEY", "fake_key"):
            with patch("app.services.transcription.settings.TRANSCRIPTION_MODEL", "whisper-large-v3-turbo"):
                result = await transcribe_audio(audio_bytes)

        # Verify the result is the text from the response
        assert result == "Hola, este es un mensaje de prueba."
        
        # Verify post was called with correct arguments
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "https://api.groq.com/openai/v1/audio/transcriptions"
        
        # Verify headers
        headers = kwargs.get("headers", {})
        assert headers.get("Authorization") == "Bearer fake_key"
        
        # Verify files and data
        files = kwargs.get("files", {})
        assert "file" in files
        assert files["file"][0] == "audio.ogg"
        assert files["file"][1] == audio_bytes
        assert files["file"][2] == "audio/ogg"
        
        data = kwargs.get("data", {})
        assert data.get("model") == "whisper-large-v3-turbo"
        assert data.get("response_format") == "json"

@pytest.mark.asyncio
async def test_transcribe_audio_http_error():
    # Simulate an error response from Groq API
    mock_response = AsyncMock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request"
    
    # raise_for_status should raise an HTTPStatusError
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/audio/transcriptions")
    def raise_err():
        raise httpx.HTTPStatusError(
            message="Bad Request", request=request, response=mock_response
        )
    mock_response.raise_for_status = raise_err

    audio_bytes = b"fake_audio_data_ogg"

    # Patch httpx.AsyncClient.post
    with patch("httpx.AsyncClient.post", return_value=mock_response):
        with patch("app.services.transcription.settings.GROQ_API_KEY", "fake_key"):
            with pytest.raises(httpx.HTTPStatusError):
                await transcribe_audio(audio_bytes)

@pytest.mark.asyncio
async def test_transcribe_audio_missing_key():
    audio_bytes = b"fake_audio_data_ogg"
    
    with patch("app.services.transcription.settings.GROQ_API_KEY", ""):
        with pytest.raises(ValueError, match="GROQ_API_KEY no está configurada"):
            await transcribe_audio(audio_bytes)
