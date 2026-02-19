from __future__ import annotations

import logging
from datetime import datetime, timedelta

from app.models.agent import Message

logger = logging.getLogger(__name__)


class ConversationMemory:
    """
    Almacenamiento en memoria del historial de conversación por usuario.
    Cada entrada expira después de `ttl_minutes` de inactividad.
    """

    def __init__(self, ttl_minutes: int = 60) -> None:
        self._store: dict[str, tuple[list[Message], datetime]] = {}
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
        logger.debug("Historial de %s borrado manualmente", phone)
