# Proposal: Telegram Channel Connection

## Intent

Abrir un segundo canal conversacional en Telegram para que el producto no dependa exclusivamente de WhatsApp. Hoy la arquitectura asume que toda identidad, memoria y mensajería pasan por números y webhooks de Meta; agregar Telegram sin rediseñar ese borde produciría una integración frágil y engañosa.

## Scope

### In Scope
- Recibir mensajes privados de texto desde Telegram Bot API mediante webhook seguro y responder por el mismo chat.
- Introducir una identidad canónica multi-canal para usuarios y memoria de conversación, preservando el comportamiento existente de WhatsApp.
- Adaptar el wiring del agente y de los servicios necesarios para que Telegram privado pueda usar el flujo financiero actual sin depender de un `whatsapp_number` real.
- Documentar configuración, límites y rollout operativo del nuevo canal.

### Out of Scope
- Soporte de grupos/canales de Telegram, inline keyboards, comandos avanzados o flujos moderados por admins.
- Procesamiento de audio, imagen, OCR, documentos o replies ricos específicos de Telegram en esta primera iteración.
- Vinculación explícita de una misma persona entre WhatsApp y Telegram dentro de una cuenta compartida.

## Approach

La integración entra como un segundo adaptador de transporte, no como un fork completo del producto. Se agrega un webhook propio de Telegram, un cliente de salida dedicado y una capa de identidad multi-canal que separa el dominio financiero de los IDs específicos de WhatsApp o Telegram. WhatsApp se mantiene como canal ya soportado y Telegram entra primero en modo privado/text-only para contener el riesgo brownfield.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `app/config.py` | Modified | Configuración y flags de Telegram, allowlists y timezone por defecto para usuarios sin teléfono. |
| `app/main.py` | Modified | Wiring del nuevo router/cliente y dependencias compartidas multi-canal. |
| `app/api/telegram_webhook.py` | New | Endpoint para validar y normalizar updates de Telegram. |
| `app/services/telegram.py` | New | Cliente saliente hacia Telegram Bot API. |
| `app/services/channel_identity.py` | New | Resolución y alta de usuarios por canal/ID externo. |
| `app/agent/core.py` | Modified | Contexto del agente, conversación y replies channel-aware. |
| `app/agent/memory.py` | Modified | Índice genérico de referencias de mensajes en lugar de `wamid`. |
| `app/agent/tools.py` | Modified | Contexto del dominio basado en identidad canónica, no solo teléfono. |
| `app/services/*.py` | Modified | Refactor selectivo de consultas que hoy dependen de `User.whatsapp_number`. |
| `app/db/models.py` | Modified | Tabla/campos de identidad multi-canal y atributos para usuarios no telefónicos. |
| `migrations/versions/` | Modified | Migración Alembic para la nueva identidad y compatibilidad hacia atrás. |
| `tests/test_telegram_webhook.py` | New | Cobertura del webhook y transporte de Telegram. |
| `tests/test_webhook.py` | Modified | Regresión de WhatsApp después del refactor multi-canal. |
| `docs/setup/local.md` | Modified | Setup local del bot de Telegram y secret del webhook. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| El refactor multi-canal rompa flujos existentes de WhatsApp | Med | Mantener WhatsApp como baseline con tests de regresión en webhook, memoria y servicios críticos. |
| Telegram no aporta teléfono y rompa reglas basadas en prefijos o allowlists actuales | High | Introducir timezone/defaults y allowlists por chat ID, separando reglas telefónicas de reglas por canal. |
| La superficie del cambio crezca demasiado por el acoplamiento actual a `whatsapp_number` | High | Limitar la primera iteración a chats privados de texto y mover los servicios a identidad canónica por etapas. |
| Diferencias semánticas entre updates de Telegram y payloads de Meta generen handlers duplicados | Med | Normalizar ambos canales hacia un contexto común de entrada/salida antes de tocar la lógica del agente. |

## Rollback Plan

La reversión puede hacerse con `git revert` de la feature y rollback de la migración Alembic asociada. El endpoint de WhatsApp no requiere ser removido ni modificado en datos históricos; el punto delicado es la nueva capa de identidad, por lo que la migración debe ser reversible y mantener compatibilidad con el `whatsapp_number` legado.

## Dependencies

- `TELEGRAM_BOT_TOKEN` y `TELEGRAM_WEBHOOK_SECRET` para habilitar tráfico real.
- Un endpoint HTTPS público dedicado para registrar el webhook del bot de Telegram.
- Definición de timezone por defecto para usuarios Telegram que no proveen teléfono.

## Success Criteria

- [ ] Un mensaje privado de texto de Telegram llega al agente y recibe respuesta en el mismo chat.
- [ ] El sistema resuelve usuarios por canal e ID externo sin mezclar sesiones de Telegram y WhatsApp.
- [ ] Los flujos actuales de WhatsApp siguen pasando sin regresiones funcionales relevantes.
- [ ] Las actualizaciones no soportadas de Telegram se descartan de forma segura y observable.
- [ ] La configuración y el rollout del nuevo canal quedan documentados para local/dev y deploy.
