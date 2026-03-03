import httpx
from app.config import settings

async def transcribe_audio(audio_bytes: bytes) -> str:
    """
    Transcribe audio bytes using Groq's Whisper API.
    Supports .ogg files.
    """
    if not settings.GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY no está configurada")
        
    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    
    headers = {
        "Authorization": f"Bearer {settings.GROQ_API_KEY}"
    }
    
    # Format: (filename, content, content_type)
    files = {
        "file": ("audio.ogg", audio_bytes, "audio/ogg")
    }
    
    data = {
        "model": settings.TRANSCRIPTION_MODEL,
        "response_format": "json"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            headers=headers,
            files=files,
            data=data,
            timeout=30.0
        )
        
        response.raise_for_status()
        
        result = response.json()
        return result.get("text", "")
