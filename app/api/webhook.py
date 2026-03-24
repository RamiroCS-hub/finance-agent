from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re

from fastapi import APIRouter, HTTPException, Query, Request, BackgroundTasks

from app.config import settings
from app.models.agent import Message
from app.services import whatsapp
from app.services import receipt_ocr
from app.services.plan_usage import check_quota, consume_quota_if_available
from app.services.paywall import (
    AUDIO_PROCESSING_QUOTA,
    MediaNotAllowed,
    PaywallException,
    build_quota_limit_message,
    check_media_allowed,
    get_plan_quota,
)
from app.services.private_media import build_media_download_error_message, process_private_media
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


def _mask_phone(phone: str | None) -> str:
    if not phone:
        return "unknown"
    if len(phone) <= 4:
        return "***"
    return f"...{phone[-4:]}"


def _mask_identifier(value: str | None) -> str:
    if not value:
        return "unknown"
    if len(value) <= 8:
        return value
    return f"{value[:6]}..."


def _normalize_mime_type(mime_type: str | None) -> str | None:
    if not mime_type:
        return None
    normalized = mime_type.split(";", 1)[0].strip().lower()
    return normalized or None


def _validate_media_policy(
    msg_type: str,
    media_metadata: dict | None,
    payload_mime_type: str | None,
) -> tuple[str | None, str | None]:
    if not media_metadata or not media_metadata.get("url"):
        return (
            "metadata_unavailable",
            "No pude validar el archivo que mandaste. Probá de nuevo 🙏",
        )

    mime_type = _normalize_mime_type(media_metadata.get("mime_type")) or _normalize_mime_type(
        payload_mime_type
    )
    if msg_type == "audio":
        allowed_types = {mime.lower() for mime in settings.WHATSAPP_ALLOWED_AUDIO_MIME_TYPES}
        max_bytes = settings.WHATSAPP_MAX_AUDIO_BYTES
    else:
        allowed_types = {mime.lower() for mime in settings.WHATSAPP_ALLOWED_IMAGE_MIME_TYPES}
        max_bytes = settings.WHATSAPP_MAX_IMAGE_BYTES

    if not mime_type or mime_type not in allowed_types:
        return (
            "unsupported_mime_type",
            "Ese tipo de archivo no está soportado para procesarlo automáticamente.",
        )

    try:
        file_size = int(media_metadata.get("file_size"))
    except (TypeError, ValueError):
        return (
            "missing_file_size",
            "No pude validar el archivo que mandaste. Probá de nuevo 🙏",
        )

    if file_size > max_bytes:
        return (
            "media_too_large",
            "El archivo es demasiado grande para procesarlo. Probá con uno más liviano.",
        )

    return None, None


def verify_webhook_signature(body: bytes, signature_header: str | None) -> None:
    if settings.WHATSAPP_ALLOW_UNSIGNED_DEV_WEBHOOKS or not settings.WHATSAPP_REQUIRE_SIGNATURE:
        return

    secret = settings.WHATSAPP_APP_SECRET
    if not secret:
        logger.error("Webhook signature verification required but WHATSAPP_APP_SECRET is empty")
        raise HTTPException(status_code=503, detail="Verificación de firma no configurada")

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
    media_mime_type: str | None = None,
    source_ref: str | None = None,
):
    try:
        from app.db.database import async_session_maker
        from app.services.group_service import ensure_group_member
        from app.services.user_service import get_or_create_user

        user_id: int | None = None
        plan_type = "FREE"
        timezone = infer_timezone_for_phone(phone)
        async with async_session_maker() as session:
            user = await get_or_create_user(session, phone)
            user_id = user.id
            plan_type = user.plan
            timezone = user.default_timezone or infer_timezone_for_phone(phone)
            if chat_type == "group" and group_id:
                await ensure_group_member(
                    session,
                    whatsapp_group_id=group_id,
                    whatsapp_number=phone,
                    group_name=group_name,
                )

            try:
                await check_media_allowed(plan_type, msg_type)
            except MediaNotAllowed:
                await whatsapp.send_text(phone, f"🚀 Ups! Tu plan actual no permite mensajes tipo {msg_type}. ¡Actualizá a PREMIUM para esto y mucho más!")
                return
            except PaywallException:
                await whatsapp.send_text(phone, "🚀 Ups! Alcanzaste un límite de tu plan. ¡Actualizá a PREMIUM para más beneficios!")
                return

            if (
                msg_type == "audio"
                and chat_type == "private"
                and get_plan_quota(plan_type, AUDIO_PROCESSING_QUOTA) is not None
            ):
                try:
                    quota_decision = await check_quota(
                        session,
                        user_id=user.id,
                        plan=plan_type,
                        quota_key=AUDIO_PROCESSING_QUOTA,
                        timezone=timezone,
                    )
                except Exception as exc:
                    logger.error("Error verificando cuota de audio para %s: %s", _mask_phone(phone), exc)
                else:
                    if not quota_decision.allowed:
                        await whatsapp.send_text(phone, build_quota_limit_message(AUDIO_PROCESSING_QUOTA))
                        return

        if msg_type == "audio" and media_id:
            audio_bytes = await whatsapp.download_media(media_id)
            if not audio_bytes:
                await whatsapp.send_text(phone, build_media_download_error_message("audio"))
                return
        elif msg_type == "image":
            reply_target = group_id if chat_type == "group" and group_id else phone
            image_bytes = await whatsapp.download_media(media_id) if media_id else None
            if not image_bytes:
                await whatsapp.send_text(reply_target, build_media_download_error_message("image"))
                return

        if msg_type in {"audio", "image"} and chat_type == "private":
            await process_private_media(
                agent=_agent,
                dispatcher=_WhatsAppDispatcherAdapter(),
                channel="whatsapp",
                recipient_id=phone,
                identity_key=phone,
                agent_input=phone,
                timezone=infer_timezone_for_phone(phone),
                msg_type=msg_type,
                media_bytes=audio_bytes if msg_type == "audio" else image_bytes,
                media_mime_type=media_mime_type,
                replied_to_id=replied_to_id,
                source_ref=source_ref,
                on_audio_success=(
                    _build_audio_quota_consumer(
                        user_id=user_id,
                        plan_type=plan_type,
                        timezone=timezone,
                    )
                    if msg_type == "audio"
                    else None
                ),
                audio_quota_exceeded_message=(
                    build_quota_limit_message(AUDIO_PROCESSING_QUOTA)
                    if msg_type == "audio"
                    else None
                ),
            )
            return

        if msg_type == "image":
            await whatsapp.send_text(reply_target, "Procesando ticket... 📸")
            candidate = await receipt_ocr.extract_receipt_candidate(
                image_bytes,
                mime_type=media_mime_type or "image/jpeg",
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
        logger.error("Error procesando mensaje de %s: %s", _mask_phone(phone), e, exc_info=True)
        try:
            reply_target = group_id if chat_type == "group" and group_id else phone
            await whatsapp.send_text(
                reply_target,
                "Hubo un error inesperado procesando tu mensaje. Intentá de nuevo 🙏",
            )
        except Exception:
            pass


class _WhatsAppDispatcherAdapter:
    async def send_text(self, channel: str, recipient_id: str, message: str) -> str | None:
        del channel
        return await whatsapp.send_text(recipient_id, message)


def _build_audio_quota_consumer(
    *,
    user_id: int | None,
    plan_type: str,
    timezone: str,
):
    async def _consume(source_ref: str | None) -> bool:
        if user_id is None or get_plan_quota(plan_type, AUDIO_PROCESSING_QUOTA) is None:
            return True

        from app.db.database import async_session_maker

        try:
            async with async_session_maker() as session:
                decision = await consume_quota_if_available(
                    session,
                    user_id=user_id,
                    plan=plan_type,
                    quota_key=AUDIO_PROCESSING_QUOTA,
                    timezone=timezone,
                    source_ref=source_ref,
                )
        except Exception as exc:
            logger.error("Error consumiendo cuota de audio para user_id=%s: %s", user_id, exc)
            return True
        return decision.allowed

    return _consume


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
        source_ref = message.get("id")
        msg_type = message.get("type", "")

        # Solo procesar mensajes de texto, audio e imagen
        if msg_type not in ["text", "audio", "image"]:
            logger.info(
                "Mensaje no soportado ignorado de %s (tipo: %s)",
                _mask_phone(phone),
                msg_type,
            )
            return {"status": "ok"}

        text = ""
        media_id = None
        is_audio = False
        is_image = False
        chat_type = "private"
        group_name = None
        media_mime_type = None

        if msg_type == "text":
            text = message["text"]["body"]
        elif msg_type == "audio":
            media_id = message["audio"]["id"]
            media_mime_type = message["audio"].get("mime_type")
            is_audio = True
            source_ref = source_ref or media_id
        elif msg_type == "image":
            media_id = message["image"]["id"]
            text = message["image"].get("caption", "")
            media_mime_type = message["image"].get("mime_type")
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
            logger.info(
                "Reply detectado. sender=%s reply=%s",
                _mask_phone(phone),
                _mask_identifier(replied_to_id),
            )

    except (KeyError, IndexError) as e:
        logger.warning("Payload inválido: %s", e)
        return {"status": "ok"}

    # Verificar whitelist (si está configurada)
    if settings.ALLOWED_PHONE_NUMBERS and phone not in settings.ALLOWED_PHONE_NUMBERS:
        logger.warning("Mensaje de número no autorizado: %s", _mask_phone(phone))
        return {"status": "ok"}

    if settings.WHATSAPP_RATE_LIMIT_ENABLED and _rate_limiter is not None:
        try:
            decision = await _rate_limiter.allow_message(phone)
        except Exception as e:
            logger.error(
                "Error evaluando rate limit para %s: %s",
                _mask_phone(phone),
                e,
                exc_info=True,
            )
        else:
            if not decision.allowed:
                logger.warning(
                    "Rate limit excedido para %s. Reintento sugerido en %ss",
                    _mask_phone(phone),
                    decision.retry_after_seconds,
                )
                if decision.should_notify:
                    background_tasks.add_task(
                        whatsapp.send_text,
                        phone,
                        build_rate_limit_message(decision.retry_after_seconds),
                    )
                return {"status": "ok"}

    if media_id and msg_type in {"audio", "image"}:
        media_metadata = await whatsapp.get_media_metadata(media_id)
        media_error_code, media_error_message = _validate_media_policy(
            msg_type,
            media_metadata,
            media_mime_type,
        )
        if media_error_code:
            reply_target = group_id if chat_type == "group" and group_id else phone
            logger.warning(
                "Media rechazada. sender=%s type=%s media=%s reason=%s",
                _mask_phone(phone),
                msg_type,
                _mask_identifier(media_id),
                media_error_code,
            )
            background_tasks.add_task(whatsapp.send_text, reply_target, media_error_message)
            return {"status": "ok"}

    if is_audio:
        logger.info(
            "Mensaje de audio recibido. sender=%s media=%s chat=%s",
            _mask_phone(phone),
            _mask_identifier(media_id),
            chat_type,
        )
    elif is_image:
        logger.info(
            "Mensaje de imagen recibido. sender=%s media=%s chat=%s caption_length=%d",
            _mask_phone(phone),
            _mask_identifier(media_id),
            chat_type,
            len(text),
        )
    else:
        logger.info(
            "Mensaje recibido. sender=%s type=text chat=%s length=%d",
            _mask_phone(phone),
            chat_type,
            len(text),
        )

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
        media_mime_type,
        source_ref,
    )

    # Meta requiere siempre 200
    return {"status": "ok"}
