from __future__ import annotations

import logging
import time

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from app.config import settings
from app.services import telegram
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

logger = logging.getLogger(__name__)
router = APIRouter()

_agent = None
_dispatcher = None
_identity_service = None
_recent_updates: dict[int, float] = {}
_UNSUPPORTED_PRIVATE_MESSAGE = (
    "En Telegram ya puedo procesar texto, audios e imagenes. "
    "Todavia no puedo analizar videos, documentos ni stickers por este canal."
)


def init_dependencies(agent, dispatcher, identity_service) -> None:
    global _agent, _dispatcher, _identity_service
    _agent = agent
    _dispatcher = dispatcher
    _identity_service = identity_service


def _mask_chat_id(chat_id: str | None) -> str:
    if not chat_id:
        return "unknown"
    if len(chat_id) <= 4:
        return "***"
    return f"...{chat_id[-4:]}"


def _mask_identifier(value: str | None) -> str:
    if not value:
        return "unknown"
    if len(value) <= 8:
        return value
    return f"{value[:6]}..."


def _ensure_telegram_configured() -> None:
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="telegram_not_configured")


def _verify_secret(request: Request) -> None:
    provided = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if provided != settings.TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="telegram_invalid_secret")


def _is_duplicate_update(update_id: int | None) -> bool:
    if update_id is None:
        return False

    now = time.monotonic()
    ttl = max(settings.TELEGRAM_UPDATE_DEDUP_TTL_SECONDS, 1)
    expired = [known_id for known_id, seen_at in _recent_updates.items() if now - seen_at > ttl]
    for known_id in expired:
        _recent_updates.pop(known_id, None)

    if update_id in _recent_updates:
        return True

    _recent_updates[update_id] = now
    return False


def _has_unsupported_private_content(message: dict) -> bool:
    unsupported_fields = (
        "video",
        "video_note",
        "document",
        "animation",
        "sticker",
    )
    return any(message.get(field) for field in unsupported_fields)


def _normalize_mime_type(mime_type: str | None) -> str | None:
    if not mime_type:
        return None
    normalized = mime_type.split(";", 1)[0].strip().lower()
    return normalized or None


def _validate_telegram_media_policy(
    msg_type: str,
    media_metadata: dict | None,
) -> tuple[str | None, str | None]:
    if not media_metadata or not media_metadata.get("file_path"):
        return (
            "metadata_unavailable",
            "No pude validar el archivo que mandaste. Probá de nuevo 🙏",
        )

    mime_type = _normalize_mime_type(media_metadata.get("mime_type"))
    if msg_type == "audio":
        allowed_types = {mime.lower() for mime in settings.TELEGRAM_ALLOWED_AUDIO_MIME_TYPES}
        max_bytes = settings.TELEGRAM_MAX_AUDIO_BYTES
    else:
        allowed_types = {mime.lower() for mime in settings.TELEGRAM_ALLOWED_IMAGE_MIME_TYPES}
        max_bytes = settings.TELEGRAM_MAX_IMAGE_BYTES

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


def _detect_private_message_type(message: dict) -> str | None:
    if message.get("text"):
        return "text"
    if message.get("voice") or message.get("audio"):
        return "audio"
    if message.get("photo"):
        return "image"
    if _has_unsupported_private_content(message):
        return "unsupported"
    return None


@router.post("/telegram/webhook")
async def receive_telegram_update(request: Request, background_tasks: BackgroundTasks):
    del background_tasks  # keep signature aligned with the existing webhook style

    _ensure_telegram_configured()
    _verify_secret(request)
    if _agent is None or _dispatcher is None or _identity_service is None:
        raise HTTPException(status_code=503, detail="telegram_not_configured")

    payload = await request.json()
    update_id = payload.get("update_id")
    if isinstance(update_id, int) and _is_duplicate_update(update_id):
        logger.info("Ignorando update duplicado de Telegram: %s", update_id)
        return {"status": "ok"}

    message = payload.get("message") or {}
    chat = message.get("chat") or {}
    from_user = message.get("from") or {}
    chat_id = str(chat.get("id") or "")
    msg_type = _detect_private_message_type(message)

    if chat.get("type") != "private":
        return {"status": "ok"}

    if not msg_type:
        return {"status": "ok"}

    if msg_type == "unsupported":
        if chat_id:
            logger.info("Mensaje privado de Telegram fuera de alcance. chat=%s", _mask_chat_id(chat_id))
            await _dispatcher.send_text("telegram", chat_id, _UNSUPPORTED_PRIVATE_MESSAGE)
        return {"status": "ok"}

    external_user_id = str(from_user.get("id") or chat_id)
    if not chat_id or not external_user_id:
        return {"status": "ok"}

    if settings.ALLOWED_TELEGRAM_CHAT_IDS and chat_id not in settings.ALLOWED_TELEGRAM_CHAT_IDS:
        logger.info("Ignorando chat de Telegram fuera de allowlist: %s", _mask_chat_id(chat_id))
        return {"status": "ok"}

    display_name = (
        from_user.get("username")
        or from_user.get("first_name")
        or from_user.get("last_name")
        or None
    )
    user_ctx = await _identity_service.resolve_private_user(
        channel="telegram",
        external_user_id=external_user_id,
        chat_id=chat_id,
        display_name=display_name,
    )

    replied_to_message = message.get("reply_to_message") or {}
    replied_to_id = replied_to_message.get("message_id")
    replied_to_id_str = str(replied_to_id) if replied_to_id is not None else None

    if msg_type in {"audio", "image"}:
        try:
            await check_media_allowed(user_ctx.plan, msg_type)
        except MediaNotAllowed:
            await _dispatcher.send_text(
                "telegram",
                chat_id,
                f"🚀 Ups! Tu plan actual no permite mensajes tipo {msg_type}. ¡Actualizá a PREMIUM para esto y mucho más!",
            )
            return {"status": "ok"}
        except PaywallException:
            await _dispatcher.send_text(
                "telegram",
                chat_id,
                "🚀 Ups! Alcanzaste un límite de tu plan. ¡Actualizá a PREMIUM para más beneficios!",
            )
            return {"status": "ok"}

        if msg_type == "audio" and get_plan_quota(user_ctx.plan, AUDIO_PROCESSING_QUOTA) is not None:
            from app.db.database import async_session_maker

            try:
                async with async_session_maker() as session:
                    quota_decision = await check_quota(
                        session,
                        user_id=user_ctx.user_id,
                        plan=user_ctx.plan,
                        quota_key=AUDIO_PROCESSING_QUOTA,
                        timezone=user_ctx.timezone,
                    )
            except Exception as exc:
                logger.error("Error verificando cuota Telegram audio para %s: %s", _mask_chat_id(chat_id), exc)
            else:
                if not quota_decision.allowed:
                    await _dispatcher.send_text(
                        "telegram",
                        chat_id,
                        build_quota_limit_message(AUDIO_PROCESSING_QUOTA),
                    )
                    return {"status": "ok"}

        media_metadata = await telegram.get_media_metadata(message)
        media_error_code, media_error_message = _validate_telegram_media_policy(
            msg_type,
            media_metadata,
        )
        if media_error_code:
            logger.warning(
                "Media Telegram rechazada. chat=%s type=%s file=%s reason=%s",
                _mask_chat_id(chat_id),
                msg_type,
                _mask_identifier(media_metadata.get("file_id") if media_metadata else "unknown"),
                media_error_code,
            )
            await _dispatcher.send_text("telegram", chat_id, media_error_message)
            return {"status": "ok"}

        media_bytes = await telegram.download_file(media_metadata["file_path"])
        if not media_bytes:
            await _dispatcher.send_text("telegram", chat_id, build_media_download_error_message(msg_type))
            return {"status": "ok"}

        await process_private_media(
            agent=_agent,
            dispatcher=_dispatcher,
            channel="telegram",
            recipient_id=chat_id,
            identity_key=user_ctx.identity_key,
            agent_input=user_ctx,
            timezone=user_ctx.timezone,
            msg_type=msg_type,
            media_bytes=media_bytes,
            media_mime_type=media_metadata.get("mime_type"),
            replied_to_id=replied_to_id_str,
            source_ref=str(message.get("message_id") or update_id or media_metadata.get("file_id") or ""),
            on_audio_success=(
                _build_audio_quota_consumer(
                    user_id=user_ctx.user_id,
                    plan_type=user_ctx.plan,
                    timezone=user_ctx.timezone,
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
        return {"status": "ok"}

    text = message.get("text")
    reply = await _agent.process(
        user_ctx,
        text,
        replied_to_id=replied_to_id_str,
        chat_type="private",
        group_id=None,
    )
    sent_message_id = await _dispatcher.send_text("telegram", chat_id, reply)
    if sent_message_id:
        _agent.memory.store_message_ref(user_ctx.identity_key, sent_message_id, reply)
    return {"status": "ok"}


def _build_audio_quota_consumer(
    *,
    user_id: int,
    plan_type: str,
    timezone: str,
):
    async def _consume(source_ref: str | None) -> bool:
        if get_plan_quota(plan_type, AUDIO_PROCESSING_QUOTA) is None:
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
            logger.error("Error consumiendo cuota Telegram audio para user_id=%s: %s", user_id, exc)
            return True
        return decision.allowed

    return _consume
