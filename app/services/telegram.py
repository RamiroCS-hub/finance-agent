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
