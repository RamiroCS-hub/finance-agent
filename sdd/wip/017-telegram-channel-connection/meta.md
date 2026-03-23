# Meta: Telegram Channel Connection

## Identificación
- **ID**: 017
- **Slug**: 017-telegram-channel-connection
- **Tipo**: feature
- **Estado**: done

## Resumen
Agregar un canal de Telegram Bot API reutilizando el asistente actual sin romper el flujo existente de WhatsApp.

## Stack detectado
- **Lenguaje**: Python
- **Framework**: FastAPI
- **Test runner**: pytest
- **Linter**: no determinado

## Git
- **Branch**: feature/telegram-channel-connection
- **Base branch**: main

## Artefactos
- [x] 1-functional/spec.md
- [x] 2-technical/spec.md
- [x] 3-tasks/tasks.json
- [x] 4-implementation/progress.md
- [x] 5-verify/report.md

## Fechas
- **Creada**: 2026-03-23
- **Última actualización**: 2026-03-23
- **Completada**: 2026-03-23

## Notas
- El ingreso/salida actual está centrado en `app/api/webhook.py` y `app/services/whatsapp.py`, con contratos y tests pensados solo para Meta WhatsApp.
- La identidad de usuario, los grupos, la memoria de conversación y varios servicios de dominio siguen acoplados a `whatsapp_number` y `whatsapp_group_id`.
- `ExpenseService` ya persiste gastos en PostgreSQL por `user_id`, pero muchos entrypoints y consultas todavía resuelven al usuario a partir de un teléfono.
- `ConversationMemory` indexa replies por `wamid`, lo que obliga a generalizar referencias de mensajes antes de soportar otro canal.
- La implementación aplicada agrega Telegram privado por texto, identidad `user_channels`, memoria genérica de replies y fallback de timezone para identidades sin teléfono.
- Telegram sigue en modo `private text only`; grupos, media, account linking cross-channel e interacciones avanzadas quedan fuera de alcance inicial.
