# Technical Spec: Telegram Channel Connection

**Feature**: 017-telegram-channel-connection
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-23
**Refs**: `1-functional/spec.md`, `2-technical/design.md`

## Architecture Overview

La solución incorpora Telegram como segundo canal HTTP del producto a través de `POST /telegram/webhook`, manteniendo a WhatsApp en `POST /webhook`. Ambos bordes convergen en un contexto de entrada común para el agente: identidad resuelta, tipo de chat, texto, referencia de reply y canal de salida. El núcleo del agente no debe distinguir “Meta vs Telegram” para la mayoría de los caminos de negocio.

El principal cambio estructural es la identidad. El sistema agrega una capa `user_channels` para resolver usuarios por `(channel, external_user_id)` y deja de asumir que toda operación parte de `User.whatsapp_number`. Eso permite soportar usuarios Telegram-only, preservar a los usuarios existentes de WhatsApp y desacoplar gradualmente el dominio financiero de los identificadores específicos de un proveedor.

Flujo propuesto:

```text
Telegram request
    ->
validate secret + parse update
    ->
private text filter
    ->
ChannelIdentityService.resolve_private_user("telegram", ...)
    ->
AgentLoop.process(user_ctx, text, replied_to_message_id)
    ->
MessageDispatcher.send_text("telegram", chat_id, reply)
```

WhatsApp sigue el mismo patrón, pero resolviendo identidad por canal `whatsapp`.

## Architecture Decision Records

### ADR-001: Usar webhook de Telegram con secret token explícito

- **Status**: Accepted
- **Context**: El proyecto ya opera sobre FastAPI y endpoints webhook para mensajería entrante.
- **Decision**: Exponer un `POST /telegram/webhook` validado por `X-Telegram-Bot-Api-Secret-Token`.
- **Consequences**: El despliegue sigue el modelo actual de webhooks; la seguridad depende de que el secret esté configurado y sincronizado con Telegram.
- **Alternatives considered**: Long polling, descartado por introducir un modelo operativo paralelo al webhook ya existente.

### ADR-002: Resolver usuarios con una tabla `user_channels`

- **Status**: Accepted
- **Context**: Múltiples servicios todavía buscan `User` por `whatsapp_number`, lo que imposibilita usuarios sin teléfono.
- **Decision**: Crear `user_channels` como fuente de verdad para identidades externas y volver `users.whatsapp_number` un campo legado/nullable.
- **Consequences**: El refactor toca servicios y tests, pero permite Telegram real y habilita futuros canales sin contaminar el modelo.
- **Alternatives considered**: Reutilizar `whatsapp_number` con prefijos sintéticos, descartado por deuda semántica y riesgos sobre timezone/validaciones.

### ADR-003: Generalizar salida y replies mediante un dispatcher

- **Status**: Accepted
- **Context**: Hoy el webhook y el agente llaman directamente a `app.services.whatsapp`.
- **Decision**: Introducir un `MessageDispatcher` con contrato uniforme `send_text(channel, recipient_id, message)`.
- **Consequences**: La salida multi-canal queda centralizada y la lógica del agente deja de depender de un proveedor específico.
- **Alternatives considered**: Duplicar código de envío por canal en cada webhook, descartado por repetición y mayor riesgo de divergencia.

### ADR-004: Limitar Telegram v1 a chats privados de texto

- **Status**: Accepted
- **Context**: La base actual solo abstrae con suficiente madurez el flujo privado textual.
- **Decision**: Procesar únicamente `message.text` de chats `private`; ignorar grupos, canales y media en esta iteración.
- **Consequences**: La feature sale con una superficie controlada y verificable; nuevas modalidades quedarán para features posteriores.
- **Alternatives considered**: Soportar grupos/media desde el primer release, descartado por costo brownfield excesivo.

## Component Design

### `app/services/channel_identity.py`

**Responsabilidad**: Resolver identidad interna y defaults operativos a partir del canal.

**Interfaz pública**:
```python
from dataclasses import dataclass

@dataclass
class ResolvedUserContext:
    user_id: int
    channel: str
    external_user_id: str
    chat_id: str
    phone_number: str | None
    timezone: str

class ChannelIdentityService:
    async def resolve_private_user(
        self,
        channel: str,
        external_user_id: str,
        chat_id: str,
        display_name: str | None = None,
    ) -> ResolvedUserContext: ...
```

**Dependencias**: `AsyncSession`, `User`, `UserChannel`, settings de timezone.

### `app/db/models.py`

**Responsabilidad**: Persistir la relación entre usuarios internos e identidades externas.

**Interfaz pública**:
```python
class UserChannel(Base):
    __tablename__ = "user_channels"
    id: Mapped[int]
    user_id: Mapped[int]
    channel: Mapped[str]
    external_user_id: Mapped[str]
    chat_id: Mapped[str]
    display_name: Mapped[str | None]
```

**Dependencias**: `User`, migraciones Alembic.

### `app/api/telegram_webhook.py`

**Responsabilidad**: Validar requests, filtrar alcance v1 y delegar al agente.

**Interfaz pública**:
```python
def init_dependencies(agent, dispatcher, identity_service, rate_limiter=None) -> None: ...
@router.post("/telegram/webhook")
async def receive_telegram_update(request: Request, background_tasks: BackgroundTasks): ...
```

**Dependencias**: `ChannelIdentityService`, `MessageDispatcher`, `AgentLoop`.

### `app/services/telegram.py`

**Responsabilidad**: Cliente saliente hacia Telegram Bot API.

**Interfaz pública**:
```python
async def send_text(chat_id: str, message: str) -> str | None: ...
```

**Dependencias**: `httpx`, `TELEGRAM_BOT_TOKEN`.

### `app/services/message_dispatch.py`

**Responsabilidad**: Encapsular el envío saliente por canal.

**Interfaz pública**:
```python
class MessageDispatcher:
    async def send_text(self, channel: str, recipient_id: str, message: str) -> str | None: ...
```

**Dependencias**: servicios `whatsapp` y `telegram`.

### `app/agent/core.py` y `app/agent/memory.py`

**Responsabilidad**: Operar con conversation keys y replies channel-aware.

**Interfaz pública**:
```python
async def process(
    self,
    user_ctx: ResolvedUserContext,
    user_text: str,
    replied_to_message_id: str | None = None,
    chat_type: str = "private",
    group_id: str | None = None,
) -> str: ...
```

**Dependencias**: `ToolRegistry`, `ConversationMemory`, `ChannelIdentityService`.

## Data Model

Cambios planificados:

```python
class User(Base):
    whatsapp_number: Mapped[str | None] = mapped_column(String, unique=True, index=True, nullable=True)
    default_timezone: Mapped[str | None] = mapped_column(String, nullable=True)

class UserChannel(Base):
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String, index=True)
    external_user_id: Mapped[str] = mapped_column(String)
    chat_id: Mapped[str] = mapped_column(String)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
```

La migración debe:
- crear `user_channels`;
- mover la resolución nueva a la tabla puente;
- permitir `users.whatsapp_number = NULL` para usuarios Telegram-only;
- backfillear registros WhatsApp existentes a `user_channels`.

## API Contract

### `POST /telegram/webhook`

**Request**:
```json
{
  "update_id": 123456789,
  "message": {
    "message_id": 42,
    "from": {
      "id": 777001,
      "first_name": "Ana"
    },
    "chat": {
      "id": 777001,
      "type": "private"
    },
    "text": "gasté 2500 en súper"
  }
}
```

**Response 200**:
```json
{"status":"ok"}
```

**Errors**:
| Status | Code | Description |
|--------|------|-------------|
| 401 | `telegram_invalid_secret` | El request no trae el secret correcto. |
| 503 | `telegram_not_configured` | Faltan token/secret o Telegram está deshabilitado. |

Sin cambios en la API pública de WhatsApp existente.

## Error Handling

- Si Telegram está deshabilitado o incompleto en config, el webhook rechaza el request con error explícito y no toca la lógica de WhatsApp.
- Si el update no es un chat privado de texto, el webhook devuelve `200 {"status":"ok"}` y lo descarta.
- Si la resolución de identidad falla, el sistema registra el incidente y no procesa el update.
- Si el envío saliente a Telegram falla, el error queda loggeado con IDs sanitizados y el update no se reprocesa.
- Las reglas que antes dependían de teléfono usan `user_ctx.phone_number` cuando exista; si no, caen a `default_timezone` u otra política explícita.

## Testing Strategy

- **Unit tests**: `tests/test_channel_identity.py`, `tests/test_telegram.py`, `tests/test_memory.py` para resolver identidad, envío y replies genéricos.
- **Integration tests**: `tests/test_telegram_webhook.py` cubre éxito, descarte por alcance y secreto inválido; `tests/test_webhook.py` asegura no regresión de WhatsApp.
- **E2E tests**: no aplica en esta iteración; queda smoke manual para registro de webhook en entorno real.

Mapeo a scenarios de `1-functional/spec.md`:

- **REQ-01 Scenario 01**: un texto privado de Telegram produce llamada al agente y envío saliente.
- **REQ-01 Scenario 02**: grupos/no-texto se descartan sin llamar al agente.
- **REQ-02 Scenario 01**: la respuesta usa el dispatcher con canal `telegram`.
- **REQ-02 Scenario 02**: una falla de `send_text` no produce doble respuesta.
- **REQ-03 Scenario 01**: la conversation key de Telegram se reutiliza entre mensajes.
- **REQ-03 Scenario 02**: IDs coincidentes entre canales no comparten memoria ni usuario.
- **REQ-04 Scenario 01**: un usuario Telegram puede registrar/consultar información usando identidad canónica.
- **REQ-04 Scenario 02**: timezone/default explícito cubre usuarios sin teléfono.
- **REQ-05 Scenario 01**: Telegram deshabilitado no toca `/webhook`.
- **REQ-05 Scenario 02**: el secret inválido retorna error y corta el procesamiento.

## Non-Functional Requirements

- **Performance**: la normalización de Telegram agrega solo validación, resolución de identidad y dispatch; no debe introducir múltiples round-trips innecesarios fuera de los ya requeridos por el agente.
- **Security**: el webhook de Telegram requiere secret explícito; los logs deben seguir el estándar sanitizado aplicado en la feature 016.
- **Observability**: registrar canal, chat type, resultado de validación y fallas salientes con IDs truncados y sin payloads completos.

## Brownfield Annotations

<!-- extends: app/api/webhook.py#receive_message -->
<!-- extends: app/agent/memory.py#ConversationMemory -->
<!-- extends: sdd/wip/016-webhook-hardening-and-privacy-controls/2-technical/spec.md#Error Handling -->
