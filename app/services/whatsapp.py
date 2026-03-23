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


async def send_text(phone_number: str, message: str) -> str | None:
    """
    Envía un mensaje de texto por WhatsApp via Meta Cloud API.
    Retorna el wamid del mensaje enviado, o None si hubo error.
    """
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
                return None
            data = response.json()
            wamid = data.get("messages", [{}])[0].get("id")
            logger.info("Mensaje enviado a %s (wamid: %s)", phone_number, wamid)
            return wamid
    except Exception as e:
        logger.error("Error enviando mensaje a %s: %s", phone_number, e)
        return None


def send_image_sync(phone_number: str, image_url: str) -> str | None:
    """
    Envía una imagen (o GIF) por WhatsApp via Meta Cloud API (versión síncrona).
    Retorna el wamid del mensaje enviado, o None si hubo error.
    """
    phone_number = _normalize_ar_phone(phone_number)
    url = f"{GRAPH_API_URL}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "image",
        "image": {"link": image_url},
    }

    try:
        with httpx.Client() as client:
            response = client.post(url, headers=headers, json=payload, timeout=10.0)
            if response.status_code >= 400:
                logger.error(
                    "WhatsApp API error %s para %s: %s",
                    response.status_code, phone_number, response.text,
                )
                return None
            data = response.json()
            wamid = data.get("messages", [{}])[0].get("id")
            logger.info("Imagen enviada a %s (wamid: %s)", phone_number, wamid)
            return wamid
    except Exception as e:
        logger.error("Error enviando imagen a %s: %s", phone_number, e)
        return None

async def upload_media(file_bytes: bytes, mime_type: str, filename: str) -> str | None:
    """
    Sube un archivo binario a WhatsApp Cloud API.
    Retorna el media_id, o None si hubo error.
    """
    url = f"{GRAPH_API_URL}/{settings.WHATSAPP_PHONE_NUMBER_ID}/media"
    headers = {"Authorization": f"Bearer {settings.WHATSAPP_TOKEN}"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=headers,
                data={"messaging_product": "whatsapp"},
                files={"file": (filename, file_bytes, mime_type)},
                timeout=30.0,
            )
            if response.status_code >= 400:
                logger.error(
                    "WhatsApp upload_media error %s: %s",
                    response.status_code,
                    response.text,
                )
                return None
            media_id = response.json().get("id")
            logger.info("Media subido correctamente (id: %s)", media_id)
            return media_id
    except Exception as e:
        logger.error("Error subiendo media a WhatsApp: %s", e)
        return None


async def send_document(
    phone_number: str,
    media_id: str,
    filename: str,
    caption: str | None = None,
) -> str | None:
    """
    Envía un documento (PDF, etc.) por WhatsApp usando un media_id previamente subido.
    Retorna el wamid del mensaje enviado, o None si hubo error.
    """
    phone_number = _normalize_ar_phone(phone_number)
    url = f"{GRAPH_API_URL}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    doc: dict = {"id": media_id, "filename": filename}
    if caption:
        doc["caption"] = caption
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "document",
        "document": doc,
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=15.0)
            if response.status_code >= 400:
                logger.error(
                    "WhatsApp send_document error %s para %s: %s",
                    response.status_code,
                    phone_number,
                    response.text,
                )
                return None
            data = response.json()
            wamid = data.get("messages", [{}])[0].get("id")
            logger.info("Documento enviado a %s (wamid: %s)", phone_number, wamid)
            return wamid
    except Exception as e:
        logger.error("Error enviando documento a %s: %s", phone_number, e)
        return None


async def download_media(media_id: str) -> bytes | None:
    """
    Descarga el contenido binario de un media_id desde WhatsApp.
    Son 2 pasos:
      1) GET a Graph API para obtener la URL real de descarga
      2) GET a la URL de descarga para obtener los bytes
    """
    url = f"{GRAPH_API_URL}/{media_id}"
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}"
    }

    try:
        async with httpx.AsyncClient() as client:
            # Step 1: Get media URL
            response = await client.get(url, headers=headers, timeout=10.0)
            response.raise_for_status()
            media_info = response.json()
            media_url = media_info.get("url")

            if not media_url:
                logger.error("No se pudo obtener la URL de descarga para el media_id %s", media_id)
                return None

            # Step 2: Download media bytes using the URL
            # We still need the Bearer token for downloading
            download_response = await client.get(media_url, headers=headers, timeout=20.0)
            download_response.raise_for_status()
            
            return download_response.content
    except httpx.HTTPError as e:
        logger.error("Error HTTP descargando media %s: %s", media_id, e)
        return None
    except Exception as e:
        logger.error("Error inesperado descargando media %s: %s", media_id, e)
        return None

