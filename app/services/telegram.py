from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def _mask_chat_id(chat_id: str | None) -> str:
    if not chat_id:
        return "unknown"
    raw = str(chat_id)
    if len(raw) <= 4:
        return "***"
    return f"...{raw[-4:]}"


def _body_length(response: httpx.Response) -> int | str:
    try:
        return len(response.text or "")
    except Exception:
        return "unknown"


def _mask_identifier(value: str | None) -> str:
    if not value:
        return "unknown"
    if len(value) <= 8:
        return value
    return f"{value[:6]}..."


async def send_text(chat_id: str, message: str) -> str | None:
    """
    Envía un mensaje de texto por Telegram Bot API.
    Retorna el message_id como string, o None si hubo error.
    """
    url = f"{settings.TELEGRAM_API_BASE_URL}/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=10.0)
            if response.status_code >= 400:
                logger.error(
                    "Telegram API error %s para chat %s. body_length=%s",
                    response.status_code,
                    _mask_chat_id(chat_id),
                    _body_length(response),
                )
                return None
            data = response.json()
            message_id = data.get("result", {}).get("message_id")
            logger.info(
                "Mensaje enviado a Telegram chat %s (message_id: %s)",
                _mask_chat_id(chat_id),
                message_id,
            )
            return str(message_id) if message_id is not None else None
    except Exception as exc:
        logger.error("Error enviando mensaje a Telegram chat %s: %s", _mask_chat_id(chat_id), exc)
        return None


async def get_file(file_id: str) -> dict | None:
    url = f"{settings.TELEGRAM_API_BASE_URL}/bot{settings.TELEGRAM_BOT_TOKEN}/getFile"
    params = {"file_id": file_id}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=10.0)
            if response.status_code >= 400:
                logger.error(
                    "Telegram getFile error %s para archivo %s. body_length=%s",
                    response.status_code,
                    _mask_identifier(file_id),
                    _body_length(response),
                )
                return None
            data = response.json()
            return data.get("result")
    except Exception as exc:
        logger.error(
            "Error obteniendo metadata de archivo Telegram %s: %s",
            _mask_identifier(file_id),
            exc,
        )
        return None


async def get_media_metadata(message: dict) -> dict | None:
    audio_payload = message.get("voice") or message.get("audio")
    if audio_payload:
        file_id = audio_payload.get("file_id")
        if not file_id:
            return None
        file_info = await get_file(file_id)
        return {
            "file_id": file_id,
            "file_path": file_info.get("file_path") if file_info else None,
            "file_size": (
                file_info.get("file_size")
                if file_info and file_info.get("file_size") is not None
                else audio_payload.get("file_size")
            ),
            "mime_type": audio_payload.get("mime_type") or "audio/ogg",
        }

    photos = message.get("photo") or []
    if photos:
        largest_photo = max(photos, key=lambda item: int(item.get("file_size") or 0))
        file_id = largest_photo.get("file_id")
        if not file_id:
            return None
        file_info = await get_file(file_id)
        return {
            "file_id": file_id,
            "file_path": file_info.get("file_path") if file_info else None,
            "file_size": (
                file_info.get("file_size")
                if file_info and file_info.get("file_size") is not None
                else largest_photo.get("file_size")
            ),
            "mime_type": "image/jpeg",
        }

    return None


async def download_file(file_path: str) -> bytes | None:
    url = f"{settings.TELEGRAM_API_BASE_URL}/file/bot{settings.TELEGRAM_BOT_TOKEN}/{file_path}"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=20.0)
            if response.status_code >= 400:
                logger.error(
                    "Telegram file download error %s para %s. body_length=%s",
                    response.status_code,
                    _mask_identifier(file_path),
                    _body_length(response),
                )
                return None
            return response.content
    except Exception as exc:
        logger.error(
            "Error descargando archivo Telegram %s: %s",
            _mask_identifier(file_path),
            exc,
        )
        return None
