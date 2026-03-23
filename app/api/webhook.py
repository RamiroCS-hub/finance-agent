from __future__ import annotations

import hashlib
import hmac
import inspect
import json
import logging
import re

from fastapi import APIRouter, HTTPException, Query, Request, BackgroundTasks

from app.config import settings
from app.models.agent import Message
from app.models.expense import ParsedExpense
from app.services.alerts import AlertService
from app.services import whatsapp
from app.services import receipt_ocr
from app.services import transcription
from app.services.timezones import infer_timezone_for_phone, local_now_for_phone

logger = logging.getLogger(__name__)
router = APIRouter()

# Inyectado desde main.py al iniciar la app
_agent = None
_rate_limiter = None


def init_dependencies(agent, rate_limiter=None) -> None:
    global _agent, _rate_limiter
    _agent = agent
    _rate_limiter = rate_limiter


def verify_webhook_signature(body: bytes, signature_header: str | None) -> None:
    secret = settings.WHATSAPP_APP_SECRET
    if not secret:
        return

    if not signature_header or not signature_header.startswith("sha256="):
        raise HTTPException(status_code=401, detail="Firma de webhook inválida")

    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    provided = signature_header.split("=", 1)[1]
    if not hmac.compare_digest(expected, provided):
        raise HTTPException(status_code=401, detail="Firma de webhook inválida")


def resolve_group_text(text: str) -> str | None:
    mentions = [settings.GROUP_BOT_MENTION, "@Tesorero"]
    for mention in mentions:
        pattern = re.compile(re.escape(mention), re.IGNORECASE)
        if pattern.search(text):
            return pattern.sub("", text).strip()
    return None


def build_rate_limit_message(retry_after_seconds: int) -> str:
    wait_seconds = max(1, retry_after_seconds)
    return (
        f"Estás mandando muchos mensajes muy rápido. Esperá {wait_seconds}s y probá de nuevo."
    )


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


async def _process_message_background(
    phone: str,
    text: str,
    replied_to_id: str | None = None,
    msg_type: str = "text",
    media_id: str | None = None,
    chat_type: str = "private",
    group_id: str | None = None,
    group_name: str | None = None,
    image_mime_type: str | None = None,
):
    try:
        from app.db.database import async_session_maker
        from app.services.group_service import ensure_group_member
        from app.services.user_service import get_or_create_user
        from app.services.paywall import check_media_allowed, MediaNotAllowed, PaywallException
        
        async with async_session_maker() as session:
            # 6.1 and 6.2 Get or create user
            user = await get_or_create_user(session, phone)
            plan_type = user.plan  # Read from database
            if chat_type == "group" and group_id:
                await ensure_group_member(
                    session,
                    whatsapp_group_id=group_id,
                    whatsapp_number=phone,
                    group_name=group_name,
                )
            
            # 6.3 Run paywall checks
            try:
                await check_media_allowed(plan_type, msg_type)
            except MediaNotAllowed as e:
                await whatsapp.send_text(phone, f"🚀 Ups! Tu plan actual no permite mensajes tipo {msg_type}. ¡Actualizá a PREMIUM para esto y mucho más!")
                return
            except PaywallException as e:
                await whatsapp.send_text(phone, "🚀 Ups! Alcanzaste un límite de tu plan. ¡Actualizá a PREMIUM para más beneficios!")
                return

        if msg_type == "audio" and media_id:
            await whatsapp.send_text(phone, "Escuchando audio... 🎧")
            audio_bytes = await whatsapp.download_media(media_id)
            if not audio_bytes:
                await whatsapp.send_text(phone, "No pude descargar el audio 😔")
                return
            
            text = await transcription.transcribe_audio(audio_bytes)
            if not text:
                await whatsapp.send_text(phone, "No pude transcribir el audio 😔")
                return
        elif msg_type == "image":
            reply_target = group_id if chat_type == "group" and group_id else phone
            await whatsapp.send_text(reply_target, "Procesando ticket... 📸")
            image_bytes = await whatsapp.download_media(media_id) if media_id else None
            if not image_bytes:
                await whatsapp.send_text(reply_target, "No pude descargar la imagen 😔")
                return

            candidate = await receipt_ocr.extract_receipt_candidate(
                image_bytes,
                mime_type=image_mime_type or "image/jpeg",
            )
            if candidate["status"] in {"error", "low_confidence"}:
                error_msg = "No pude extraer datos confiables del ticket. Probá con una foto más clara o registralo por texto."
                await whatsapp.send_text(reply_target, error_msg)
                memory_key = f"group:{group_id}" if chat_type == "group" and group_id else phone
                history = _agent.memory.get(memory_key)
                history.append(Message(role="user", content="[El usuario envió una foto de un ticket]"))
                history.append(Message(role="assistant", content=error_msg))
                _agent.memory.append(memory_key, history)
                return

            if candidate["status"] == "needs_confirmation":
                amount = candidate.get("amount")
                shop = candidate.get("shop") or "ese comercio"
                confirmation_msg = (
                    f"Veo un ticket por *${amount}* en *{shop}*. "
                    f"Si está bien, mandame por texto: `{amount} {shop}`"
                )
                wamid = await whatsapp.send_text(reply_target, confirmation_msg)
                memory_key = f"group:{group_id}" if chat_type == "group" and group_id else phone
                if wamid:
                    _agent.memory.store_wamid(memory_key, wamid, confirmation_msg)
                history = _agent.memory.get(memory_key)
                history.append(Message(role="user", content="[El usuario envió una foto de un ticket]"))
                history.append(Message(role="assistant", content=confirmation_msg))
                _agent.memory.append(memory_key, history)
                return

            amount = float(candidate["amount"])
            shop = candidate.get("shop")
            category = candidate.get("category") or "Otros"
            description = shop or "ticket"

            if chat_type == "group" and group_id:
                result = await _agent.group_expense_service.register_group_expense(
                    whatsapp_group_id=group_id,
                    payer_phone=phone,
                    amount=amount,
                    description=description,
                    category=category,
                    currency=settings.DEFAULT_CURRENCY,
                    shop=shop,
                    spent_at=local_now_for_phone(phone),
                    source_timezone=infer_timezone_for_phone(phone),
                )
                if not result.get("success"):
                    await whatsapp.send_text(reply_target, "No pude registrar el gasto del ticket 😔")
                    return
                confirmation = f"✅ Registré *${amount}* en *{shop or description}* para el grupo"
            else:
                expense = ParsedExpense(
                    amount=amount,
                    description=description,
                    category=category,
                    currency=settings.DEFAULT_CURRENCY,
                    raw_message=candidate.get("detected_text") or "ticket ocr",
                    shop=shop,
                    spent_at=local_now_for_phone(phone),
                    source_timezone=infer_timezone_for_phone(phone),
                    source="ocr",
                )
                store_result = _agent.expense_store.append_expense(phone, expense)
                if inspect.isawaitable(store_result):
                    store_result = await store_result
                if not store_result:
                    await whatsapp.send_text(reply_target, "No pude registrar el gasto del ticket 😔")
                    return
                confirmation = f"✅ Registré *${amount}* en *{shop or description}*"
                try:
                    alerts = await AlertService().evaluate_expense_alerts(
                        phone,
                        amount=amount,
                        category=category,
                        spent_at=store_result.spent_at,
                    )
                    if alerts:
                        confirmation += " • " + " ".join(
                            alert["message"] for alert in alerts
                        )
                except Exception as e:
                    logger.error("Error evaluando alertas OCR para %s: %s", phone, e)

            memory_key = f"group:{group_id}" if chat_type == "group" and group_id else phone
            wamid = await whatsapp.send_text(reply_target, confirmation)
            if wamid:
                _agent.memory.store_wamid(memory_key, wamid, confirmation)
            history = _agent.memory.get(memory_key)
            history.append(Message(role="user", content="[El usuario envió una foto de un ticket]"))
            history.append(Message(role="assistant", content=confirmation))
            _agent.memory.append(memory_key, history)
            return

        reply = await _agent.process(
            phone,
            text,
            replied_to_id=replied_to_id,
            chat_type=chat_type,
            group_id=group_id,
        )
        if reply:
            reply_target = group_id if chat_type == "group" and group_id else phone
            wamid = await whatsapp.send_text(reply_target, reply)
            if wamid:
                memory_key = f"group:{group_id}" if chat_type == "group" and group_id else phone
                _agent.memory.store_wamid(memory_key, wamid, reply)
    except Exception as e:
        logger.error("Error procesando mensaje de %s: %s", phone, e, exc_info=True)
        try:
            reply_target = group_id if chat_type == "group" and group_id else phone
            await whatsapp.send_text(
                reply_target,
                "Hubo un error inesperado procesando tu mensaje. Intentá de nuevo 🙏",
            )
        except Exception:
            pass


@router.post("/webhook")
async def receive_message(request: Request, background_tasks: BackgroundTasks):
    """Recepción de mensajes entrantes de WhatsApp."""
    body_bytes = await request.body()
    verify_webhook_signature(body_bytes, request.headers.get("X-Hub-Signature-256"))
    try:
        body = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
    except json.JSONDecodeError:
        logger.warning("Payload JSON inválido")
        return {"status": "ok"}

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

        # Solo procesar mensajes de texto, audio e imagen
        if msg_type not in ["text", "audio", "image"]:
            logger.info("Mensaje no soportado ignorado de %s (tipo: %s)", phone, msg_type)
            return {"status": "ok"}

        text = ""
        media_id = None
        is_audio = False
        is_image = False
        chat_type = "private"
        group_name = None
        image_mime_type = None

        if msg_type == "text":
            text = message["text"]["body"]
        elif msg_type == "audio":
            media_id = message["audio"]["id"]
            is_audio = True
        elif msg_type == "image":
            media_id = message["image"]["id"]
            text = message["image"].get("caption", "")
            image_mime_type = message["image"].get("mime_type")
            is_image = True

        # Check if it's a group chat (indicated by the presence of group_id)
        group_id = message.get("group_id")
        if group_id:
            chat_type = "group"
            group_name = message.get("group_name") or value.get("metadata", {}).get("display_phone_number")
            cleaned_text = resolve_group_text(text)
            if cleaned_text is None:
                logger.info("Ignorando mensaje de grupo %s sin mención al bot", group_id)
                return {"status": "ok"}
            text = cleaned_text

        # Detectar si el usuario respondió a un mensaje específico (reply nativo de WhatsApp)
        replied_to_id: str | None = message.get("context", {}).get("id")
        if replied_to_id:
            logger.info("Reply detectado de %s → wamid referenciado: %s", phone, replied_to_id)

    except (KeyError, IndexError) as e:
        logger.warning("Payload inválido: %s", e)
        return {"status": "ok"}

    # Verificar whitelist (si está configurada)
    if settings.ALLOWED_PHONE_NUMBERS and phone not in settings.ALLOWED_PHONE_NUMBERS:
        logger.warning("Mensaje de número no autorizado: %s", phone)
        return {"status": "ok"}

    if settings.WHATSAPP_RATE_LIMIT_ENABLED and _rate_limiter is not None:
        try:
            decision = await _rate_limiter.allow_message(phone)
        except Exception as e:
            logger.error("Error evaluando rate limit para %s: %s", phone, e, exc_info=True)
        else:
            if not decision.allowed:
                logger.warning(
                    "Rate limit excedido para %s. Reintento sugerido en %ss",
                    phone,
                    decision.retry_after_seconds,
                )
                if decision.should_notify:
                    background_tasks.add_task(
                        whatsapp.send_text,
                        phone,
                        build_rate_limit_message(decision.retry_after_seconds),
                    )
                return {"status": "ok"}

    if is_audio:
        logger.info("Mensaje de audio recibido de %s: media_id %s", phone, media_id)
    elif is_image:
        logger.info("Mensaje de imagen recibido de %s: media_id %s", phone, media_id)
    else:
        logger.info("Mensaje recibido de %s: %s", phone, text)

    # Encolar procesamiento en background
    background_tasks.add_task(
        _process_message_background, 
        phone, 
        text, 
        replied_to_id, 
        msg_type, 
        media_id,
        chat_type,
        group_id,
        group_name,
        image_mime_type,
    )

    # Meta requiere siempre 200
    return {"status": "ok"}
