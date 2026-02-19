from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

GRAPH_API_URL = "https://graph.facebook.com/v21.0"


def _normalize_ar_phone(phone: str) -> str:
    """Normaliza números argentinos: 5491112345678 → 541112345678 (quita el 9 después del 54)."""
    if phone.startswith("549") and len(phone) == 13:
        return "54" + phone[3:]
    return phone


async def send_text(phone_number: str, message: str) -> bool:
    """Envía un mensaje de texto por WhatsApp via Meta Cloud API."""
    phone_number = _normalize_ar_phone(phone_number)
    url = f"{GRAPH_API_URL}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "text",
        "text": {"body": message},
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=10.0)
            if response.status_code >= 400:
                logger.error(
                    "WhatsApp API error %s para %s: %s",
                    response.status_code, phone_number, response.text,
                )
                return False
            logger.info("Mensaje enviado a %s", phone_number)
            return True
    except Exception as e:
        logger.error("Error enviando mensaje a %s: %s", phone_number, e)
        return False
