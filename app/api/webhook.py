from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Request

from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# Inyectado desde main.py al iniciar la app
_agent = None


def init_dependencies(agent) -> None:
    global _agent
    _agent = agent


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    """Verificación del webhook (challenge de Meta)."""
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        logger.info("Webhook verificado correctamente")
        return int(hub_challenge) if hub_challenge.isdigit() else hub_challenge
    raise HTTPException(status_code=403, detail="Token de verificación inválido")


@router.post("/webhook")
async def receive_message(request: Request):
    """Recepción de mensajes entrantes de WhatsApp."""
    body = await request.json()

    # Extraer mensaje del payload de Meta
    try:
        entry = body["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]

        # Ignorar si no hay mensajes (ej: status updates)
        if "messages" not in value:
            return {"status": "ok"}

        message = value["messages"][0]
        phone = message["from"]
        msg_type = message.get("type", "")

        # Solo procesar mensajes de texto
        if msg_type != "text":
            logger.info("Mensaje no-texto ignorado de %s (tipo: %s)", phone, msg_type)
            return {"status": "ok"}

        text = message["text"]["body"]
    except (KeyError, IndexError) as e:
        logger.warning("Payload inválido: %s", e)
        return {"status": "ok"}

    # Verificar whitelist (si está configurada)
    if settings.ALLOWED_PHONE_NUMBERS and phone not in settings.ALLOWED_PHONE_NUMBERS:
        logger.warning("Mensaje de número no autorizado: %s", phone)
        return {"status": "ok"}

    logger.info("Mensaje recibido de %s: %s", phone, text)

    # Procesar con el agente y responder
    try:
        from app.services import whatsapp

        reply = await _agent.process(phone, text)
        if reply:
            await whatsapp.send_text(phone, reply)
    except Exception as e:
        logger.error("Error procesando mensaje de %s: %s", phone, e, exc_info=True)

    # Meta requiere siempre 200
    return {"status": "ok"}
