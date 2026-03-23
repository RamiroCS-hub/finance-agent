from __future__ import annotations

from app.services import telegram, whatsapp


class MessageDispatcher:
    async def send_text(self, channel: str, recipient_id: str, message: str) -> str | None:
        if channel == "telegram":
            return await telegram.send_text(recipient_id, message)
        if channel == "whatsapp":
            return await whatsapp.send_text(recipient_id, message)
        raise ValueError(f"Canal no soportado: {channel}")
