from __future__ import annotations

import logging
from datetime import datetime, timedelta

from app.models.agent import Message

logger = logging.getLogger(__name__)


class ConversationMemory:
    """
    Almacenamiento en memoria del historial de conversación por usuario.
    Cada entrada expira después de `ttl_minutes` de inactividad.
    También indexa mensajes enviados por wamid para soportar el reply nativo de WhatsApp.
    """

    def __init__(self, ttl_minutes: int = 60) -> None:
        self._store: dict[str, tuple[list[Message], datetime]] = {}
        self._message_ref_index: dict[str, dict[str, str]] = {}  # conversation_key → {message_id: texto}
        self._ttl = timedelta(minutes=ttl_minutes)

    def get(self, phone: str) -> list[Message]:
        """
        Devuelve el historial del usuario.
        Retorna lista vacía si no existe o si expiró el TTL.
        """
        if phone not in self._store:
            return []
        messages, last_active = self._store[phone]
        if datetime.now() - last_active > self._ttl:
            del self._store[phone]
            logger.debug("Historial de %s expirado (TTL)", phone)
            return []
        return list(messages)  # copia defensiva

    def append(self, phone: str, messages: list[Message]) -> None:
        """Reemplaza el historial completo y renueva el TTL."""
        self._store[phone] = (list(messages), datetime.now())

    def clear(self, phone: str) -> None:
        """Borra el historial manualmente (ej: usuario pide 'nueva conversación')."""
        self._store.pop(phone, None)
        self._message_ref_index.pop(phone, None)
        logger.debug("Historial de %s borrado manualmente", phone)

    def store_message_ref(self, conversation_key: str, message_id: str, text: str) -> None:
        """Guarda el texto de un mensaje enviado, indexado por el id nativo del canal."""
        if conversation_key not in self._message_ref_index:
            self._message_ref_index[conversation_key] = {}
        self._message_ref_index[conversation_key][message_id] = text

    def get_by_message_ref(self, conversation_key: str, message_id: str) -> str | None:
        """
        Retorna el texto de un mensaje previamente enviado dado su id nativo del canal.
        Retorna None si el ID no está en el índice (mensaje antiguo o fuera de sesión).
        """
        return self._message_ref_index.get(conversation_key, {}).get(message_id)

    # Compatibilidad con código/tests viejos de WhatsApp.
    def store_wamid(self, phone: str, wamid: str, text: str) -> None:
        self.store_message_ref(phone, wamid, text)

    def get_by_wamid(self, phone: str, wamid: str) -> str | None:
        return self.get_by_message_ref(phone, wamid)
