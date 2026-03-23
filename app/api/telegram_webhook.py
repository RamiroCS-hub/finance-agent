from __future__ import annotations

import logging
import time

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

_agent = None
_dispatcher = None
_identity_service = None
_recent_updates: dict[int, float] = {}


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
    text = message.get("text")

    if chat.get("type") != "private" or not text:
        return {"status": "ok"}

    chat_id = str(chat.get("id") or "")
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
    reply = await _agent.process(
        user_ctx,
        text,
        replied_to_id=str(replied_to_id) if replied_to_id is not None else None,
        chat_type="private",
        group_id=None,
    )
    sent_message_id = await _dispatcher.send_text("telegram", chat_id, reply)
    if sent_message_id:
        _agent.memory.store_message_ref(user_ctx.identity_key, sent_message_id, reply)
    return {"status": "ok"}
