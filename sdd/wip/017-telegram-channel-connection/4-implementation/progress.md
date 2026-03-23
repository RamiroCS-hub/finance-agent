# Implementation Progress: Telegram Channel Connection

## Estado

- Fecha: 2026-03-23
- Resultado: implementación aplicada

## Cambios realizados

- Extendí [app/db/models.py](/Users/rcarnicer/Desktop/anotamelo/app/db/models.py) con `UserChannel`, `default_timezone` y `whatsapp_number` nullable, y agregué la migración [b9c2e7f4a1de_add_user_channels_for_multi_channel_identity.py](/Users/rcarnicer/Desktop/anotamelo/migrations/versions/b9c2e7f4a1de_add_user_channels_for_multi_channel_identity.py).
- Reemplacé la resolución de usuarios en [app/services/user_service.py](/Users/rcarnicer/Desktop/anotamelo/app/services/user_service.py) por una capa canónica que entiende identidades legacy de WhatsApp y claves tipo `telegram:<id>`.
- Agregué [app/services/channel_identity.py](/Users/rcarnicer/Desktop/anotamelo/app/services/channel_identity.py), [app/services/telegram.py](/Users/rcarnicer/Desktop/anotamelo/app/services/telegram.py) y [app/services/message_dispatch.py](/Users/rcarnicer/Desktop/anotamelo/app/services/message_dispatch.py) para resolver usuarios y enviar respuestas por el canal correcto.
- Sumé el webhook [app/api/telegram_webhook.py](/Users/rcarnicer/Desktop/anotamelo/app/api/telegram_webhook.py) y lo cableé en [app/main.py](/Users/rcarnicer/Desktop/anotamelo/app/main.py) junto con las nuevas dependencias de Telegram.
- Generalicé replies y memoria en [app/agent/memory.py](/Users/rcarnicer/Desktop/anotamelo/app/agent/memory.py) y [app/agent/core.py](/Users/rcarnicer/Desktop/anotamelo/app/agent/core.py), manteniendo compatibilidad con los helpers viejos de `wamid`.
- Ajusté [app/agent/tools.py](/Users/rcarnicer/Desktop/anotamelo/app/agent/tools.py), [app/agent/skills.py](/Users/rcarnicer/Desktop/anotamelo/app/agent/skills.py) y varios servicios de dominio para que resuelvan usuario por identidad canónica, además de bloquear explícitamente funciones media-only en Telegram v1.
- Actualicé [docs/setup/local.md](/Users/rcarnicer/Desktop/anotamelo/docs/setup/local.md) y [README.md](/Users/rcarnicer/Desktop/anotamelo/README.md) con variables nuevas, endpoint y límites de alcance.
- Añadí cobertura en [tests/test_channel_identity.py](/Users/rcarnicer/Desktop/anotamelo/tests/test_channel_identity.py), [tests/test_telegram.py](/Users/rcarnicer/Desktop/anotamelo/tests/test_telegram.py), [tests/test_telegram_webhook.py](/Users/rcarnicer/Desktop/anotamelo/tests/test_telegram_webhook.py) y [tests/test_db_models.py](/Users/rcarnicer/Desktop/anotamelo/tests/test_db_models.py).

## Notas

- El canal de Telegram queda disponible solo para chats privados de texto; reportes PDF, imágenes y otros envíos ricos permanecen exclusivos de WhatsApp.
- La compatibilidad con WhatsApp se mantuvo sin cambiar el shape externo de su webhook ni su allowlist actual.
- La resolución nueva usa `user_channels`, pero acepta todavía números de WhatsApp legacy para no forzar un refactor masivo de todos los callers en una sola vez.
