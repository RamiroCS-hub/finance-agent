from __future__ import annotations

import inspect
import logging
from datetime import datetime
from typing import Awaitable, Callable
from zoneinfo import ZoneInfo

from app.agent.core import AgentLoop
from app.config import settings
from app.models.agent import Message
from app.models.expense import ParsedExpense
from app.services import receipt_ocr, transcription
from app.services.alerts import AlertService
from app.services.message_dispatch import MessageDispatcher

logger = logging.getLogger(__name__)

_AUDIO_PROGRESS_MESSAGE = "Escuchando audio... 🎧"
_AUDIO_DOWNLOAD_ERROR_MESSAGE = "No pude descargar el audio 😔"
_AUDIO_TRANSCRIPTION_ERROR_MESSAGE = "No pude transcribir el audio 😔"
_IMAGE_PROGRESS_MESSAGE = "Procesando ticket... 📸"
_IMAGE_DOWNLOAD_ERROR_MESSAGE = "No pude descargar la imagen 😔"
_IMAGE_LOW_CONFIDENCE_MESSAGE = (
    "No pude extraer datos confiables del ticket. Probá con una foto más clara o registralo por texto."
)
_IMAGE_STORE_ERROR_MESSAGE = "No pude registrar el gasto del ticket 😔"


def build_media_download_error_message(msg_type: str) -> str:
    return _AUDIO_DOWNLOAD_ERROR_MESSAGE if msg_type == "audio" else _IMAGE_DOWNLOAD_ERROR_MESSAGE


async def process_private_media(
    *,
    agent: AgentLoop,
    dispatcher: MessageDispatcher,
    channel: str,
    recipient_id: str,
    identity_key: str,
    agent_input,
    timezone: str,
    msg_type: str,
    media_bytes: bytes,
    media_mime_type: str | None,
    replied_to_id: str | None = None,
    source_ref: str | None = None,
    on_audio_success: Callable[[str | None], Awaitable[bool]] | None = None,
    audio_quota_exceeded_message: str | None = None,
) -> None:
    if msg_type == "audio":
        await dispatcher.send_text(channel, recipient_id, _AUDIO_PROGRESS_MESSAGE)
        try:
            text = await transcription.transcribe_audio(media_bytes)
        except Exception as exc:
            logger.error("Error transcribiendo audio para %s: %s", identity_key, exc)
            text = ""

        if not text:
            await dispatcher.send_text(channel, recipient_id, _AUDIO_TRANSCRIPTION_ERROR_MESSAGE)
            return

        if on_audio_success is not None:
            allowed = await on_audio_success(source_ref)
            if not allowed:
                if audio_quota_exceeded_message:
                    await dispatcher.send_text(channel, recipient_id, audio_quota_exceeded_message)
                return

        reply = await agent.process(
            agent_input,
            text,
            replied_to_id=replied_to_id,
            chat_type="private",
            group_id=None,
        )
        if reply:
            sent_message_id = await dispatcher.send_text(channel, recipient_id, reply)
            if sent_message_id:
                agent.memory.store_message_ref(identity_key, sent_message_id, reply)
        return

    if msg_type != "image":
        raise ValueError(f"Tipo de media privada no soportado: {msg_type}")

    await dispatcher.send_text(channel, recipient_id, _IMAGE_PROGRESS_MESSAGE)
    candidate = await receipt_ocr.extract_receipt_candidate(
        media_bytes,
        mime_type=media_mime_type or "image/jpeg",
    )

    if candidate["status"] in {"error", "low_confidence"}:
        sent_message_id = await dispatcher.send_text(
            channel,
            recipient_id,
            _IMAGE_LOW_CONFIDENCE_MESSAGE,
        )
        if sent_message_id:
            agent.memory.store_message_ref(identity_key, sent_message_id, _IMAGE_LOW_CONFIDENCE_MESSAGE)
        _append_memory_event(
            agent,
            identity_key,
            "[El usuario envió una foto de un ticket]",
            _IMAGE_LOW_CONFIDENCE_MESSAGE,
        )
        return

    if candidate["status"] == "needs_confirmation":
        amount = candidate.get("amount")
        shop = candidate.get("shop") or "ese comercio"
        confirmation_msg = (
            f"Veo un ticket por *${amount}* en *{shop}*. "
            f"Si está bien, mandame por texto: `{amount} {shop}`"
        )
        sent_message_id = await dispatcher.send_text(channel, recipient_id, confirmation_msg)
        if sent_message_id:
            agent.memory.store_message_ref(identity_key, sent_message_id, confirmation_msg)
        _append_memory_event(
            agent,
            identity_key,
            "[El usuario envió una foto de un ticket]",
            confirmation_msg,
        )
        return

    amount = float(candidate["amount"])
    shop = candidate.get("shop")
    category = candidate.get("category") or "Otros"
    description = shop or "ticket"
    expense = ParsedExpense(
        amount=amount,
        description=description,
        category=category,
        currency=settings.DEFAULT_CURRENCY,
        raw_message=candidate.get("detected_text") or "ticket ocr",
        shop=shop,
        spent_at=datetime.now(ZoneInfo(timezone)),
        source_timezone=timezone,
        source="ocr",
    )

    store_result = agent.expense_store.append_expense(identity_key, expense)
    if inspect.isawaitable(store_result):
        store_result = await store_result

    if not store_result:
        await dispatcher.send_text(channel, recipient_id, _IMAGE_STORE_ERROR_MESSAGE)
        return

    confirmation = f"✅ Registré *${amount}* en *{shop or description}*"
    try:
        alerts = await AlertService().evaluate_expense_alerts(
            identity_key,
            amount=amount,
            category=category,
            spent_at=store_result.spent_at,
        )
        if alerts:
            confirmation += " • " + " ".join(alert["message"] for alert in alerts)
    except Exception as exc:
        logger.error("Error evaluando alertas OCR para %s: %s", identity_key, exc)

    sent_message_id = await dispatcher.send_text(channel, recipient_id, confirmation)
    if sent_message_id:
        agent.memory.store_message_ref(identity_key, sent_message_id, confirmation)
    _append_memory_event(
        agent,
        identity_key,
        "[El usuario envió una foto de un ticket]",
        confirmation,
    )


def _append_memory_event(
    agent: AgentLoop,
    conversation_key: str,
    user_content: str,
    assistant_content: str,
) -> None:
    history = agent.memory.get(conversation_key)
    history.append(Message(role="user", content=user_content))
    history.append(Message(role="assistant", content=assistant_content))
    agent.memory.append(conversation_key, history)
