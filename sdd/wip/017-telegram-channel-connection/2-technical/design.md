## Design Document

**Feature**: 017-telegram-channel-connection
**Diseñado por**: sdd-designer
**Fecha**: 2026-03-23

### Architecture Overview

La solución agrega un segundo borde HTTP `POST /telegram/webhook` en paralelo al webhook actual de Meta, pero evita bifurcar el núcleo del producto. Telegram y WhatsApp se normalizan a un contexto común de mensaje entrante con `channel`, `external_user_id`, `chat_id`, `chat_type`, `text` y `reply_to_message_id`, y luego reutilizan el mismo `AgentLoop`.

El cambio de verdad está en la identidad: hoy la mayor parte del código asume `User.whatsapp_number`. Para que Telegram privado sea real y no un parche, la identidad de usuario debe resolverse por una tabla puente multi-canal y el dominio debe operar sobre `user_id`/`UserContext`, no sobre un teléfono crudo. WhatsApp sigue funcionando sobre la misma base, pero deja de ser la única fuente de identidad.

```text
Telegram update / WhatsApp payload
    -> channel-specific webhook validation
    -> normalize inbound message
    -> ChannelIdentityService.resolve(...)
    -> AgentLoop.process(user_context, message_context)
    -> MessageDispatcher.send_text(channel, recipient, reply)
```

### ADRs

#### ADR-001: Telegram entra por webhook seguro, no por polling

- **Context**: El producto ya opera con FastAPI expuesto por webhook y necesita compatibilidad operacional con el canal actual.
- **Decision**: Implementar Telegram mediante `POST /telegram/webhook` validado con `X-Telegram-Bot-Api-Secret-Token`.
- **Consequences**: Se conserva el patrón HTTP existente y el mismo modelo de despliegue; el entorno debe registrar el webhook y mantener el secret sincronizado.
- **Alternatives considered**: Long polling. Se descarta porque agrega un worker de polling distinto al patrón actual y complica despliegue/observabilidad.

#### ADR-002: Introducir identidad multi-canal con tabla puente

- **Context**: `users.whatsapp_number` y `groups.whatsapp_group_id` hoy están embebidos en múltiples queries y servicios.
- **Decision**: Agregar una tabla `user_channels` y tratar `users.whatsapp_number` como campo legado/compatibilidad, permitiendo usuarios Telegram sin teléfono. Las consultas nuevas deben resolver primero una identidad canónica y luego trabajar por `user_id`.
- **Consequences**: El refactor es más amplio, pero evita modelar Telegram como “un falso número de WhatsApp” y reduce deuda futura para otros canales.
- **Alternatives considered**: Guardar `telegram:<id>` dentro de `whatsapp_number`. Se descarta porque contamina semántica, rompe inferencias basadas en prefijos y perpetúa el acoplamiento.

#### ADR-003: Generalizar memoria y referencias de mensajes por canal

- **Context**: `ConversationMemory` y varios flujos de reply indexan solo `wamid`, que es un concepto específico de WhatsApp.
- **Decision**: Generalizar las claves de conversación y el índice de mensajes enviados a un identificador genérico por canal, manteniendo el mismo TTL y contrato observable del agente.
- **Consequences**: Replies y memoria quedan listos para Telegram y futuros canales; los tests actuales deben migrar de `wamid` a referencias genéricas sin perder cobertura.
- **Alternatives considered**: Mantener memoria específica por canal con dos implementaciones distintas. Se descarta por duplicación y riesgo de divergencia funcional.

#### ADR-004: Telegram v1 se limita a chat privado de texto

- **Context**: Telegram soporta grupos, media y superficies interactivas que el producto actual no abstrae todavía.
- **Decision**: Aceptar solo mensajes privados de texto en la primera iteración y descartar el resto con handling explícito.
- **Consequences**: La feature sale con alcance realista y menos riesgo brownfield; grupos, audio, OCR y mensajes enriquecidos quedan para una siguiente feature.
- **Alternatives considered**: Soporte simultáneo de grupos y media. Se descarta porque multiplicaría la complejidad antes de tener la capa multi-canal estabilizada.

### Component Design

#### `app/services/channel_identity.py`

**Responsabilidad**: Resolver o crear usuarios internos a partir de un canal y un identificador externo, devolviendo un contexto canónico reutilizable por el dominio.

**Interfaz pública**:
```python
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

**Dependencias**: `AsyncSession`, `User`, `UserChannel`, configuración de timezone/defaults.

**Invariantes**:
- La combinación `(channel, external_user_id)` es única.
- Un usuario Telegram puede no tener teléfono.
- El contexto resuelto siempre expone un `user_id` y un `timezone` utilizable.

#### `app/api/telegram_webhook.py`

**Responsabilidad**: Validar requests de Telegram, normalizar updates soportados y encolarlos al agente sin duplicar la lógica de WhatsApp.

**Interfaz pública**:
```python
def init_dependencies(agent, dispatcher, identity_service, rate_limiter=None) -> None: ...
@router.post("/telegram/webhook")
async def receive_telegram_update(request: Request, background_tasks: BackgroundTasks): ...
```

**Dependencias**: `ChannelIdentityService`, `MessageDispatcher`, `AgentLoop`, `BackgroundTasks`.

**Invariantes**:
- Solo procesa chats privados de texto en v1.
- Devuelve `200 {"status":"ok"}` para updates válidos aunque sean descartados por alcance.
- Nunca impacta el endpoint `/webhook` de WhatsApp.

#### `app/services/telegram.py`

**Responsabilidad**: Enviar mensajes de texto hacia Telegram Bot API y mapear errores de proveedor a logs operativos.

**Interfaz pública**:
```python
async def send_text(chat_id: str, message: str) -> str | None: ...
```

**Dependencias**: `httpx`, settings de Telegram.

**Invariantes**:
- El canal de salida usa `chat_id`, no teléfono.
- Los logs no exponen contenido sensible completo.

#### `app/services/message_dispatch.py`

**Responsabilidad**: Seleccionar el adaptador saliente correcto según el canal.

**Interfaz pública**:
```python
class MessageDispatcher:
    async def send_text(self, channel: str, recipient_id: str, message: str) -> str | None: ...
```

**Dependencias**: `app/services/whatsapp.py`, `app/services/telegram.py`.

**Invariantes**:
- Un mensaje nunca sale por un canal distinto al de origen.
- El contrato de retorno del dispatcher es uniforme para todos los canales.

#### `app/agent/core.py` y `app/agent/memory.py`

**Responsabilidad**: Mantener conversación, replies y contexto del usuario por canal.

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

def store_message_ref(conversation_key: str, message_id: str, text: str) -> None: ...
def get_by_message_ref(conversation_key: str, message_id: str) -> str | None: ...
```

**Dependencias**: `ChannelIdentityService`, `MessageDispatcher`, herramientas de dominio.

**Invariantes**:
- La conversation key siempre incluye canal.
- Las referencias a replies no dependen de `wamid`.
- Los servicios de dominio reciben identidad canónica o `user_id`, no un teléfono obligatorio.

### Data Model Changes

- Nueva tabla `user_channels` con columnas mínimas: `id`, `user_id`, `channel`, `external_user_id`, `chat_id`, `display_name`, `created_at`.
- Constraint único por `(channel, external_user_id)`.
- `users.whatsapp_number` pasa a ser nullable para admitir usuarios Telegram-only mientras convive con el legado.
- Nueva fuente explícita para timezone/defaults del usuario cuando no existe inferencia por teléfono.

### API Contract

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
| 401 | `telegram_invalid_secret` | El header secreto no coincide o falta. |
| 503 | `telegram_not_configured` | Telegram está deshabilitado o incompleto en config. |

### Testing Strategy

**Unit tests**:
- Resolver identidad multi-canal, defaults y deduplicación de `user_channels`.
- Dispatcher y cliente de Telegram en paths de éxito/error.
- Memoria genérica por canal y lookup de replies por referencia de mensaje.

**Integration tests**:
- `POST /telegram/webhook` en caso feliz, descarte de grupos/no-texto y error de secreto.
- Regresión de `POST /webhook` para WhatsApp después del refactor.
- Servicios que hoy consultan por `whatsapp_number` migrados a `user_id`/contexto canónico.

**Mapping a scenarios funcionales**:
| Scenario | Test type | Qué valida |
|----------|-----------|------------|
| REQ-01 Scenario 01 | integration | Un texto privado de Telegram llega al agente y dispara respuesta. |
| REQ-01 Scenario 02 | integration | Updates fuera de alcance no invocan al agente. |
| REQ-02 Scenario 01 | integration | La respuesta sale por Telegram al mismo chat. |
| REQ-02 Scenario 02 | unit/integration | Falla saliente queda loggeada sin duplicar reply. |
| REQ-03 Scenario 01 | unit | La conversación de Telegram reutiliza su propia session key. |
| REQ-03 Scenario 02 | unit/integration | IDs equivalentes entre canales no mezclan memoria ni usuarios. |
| REQ-04 Scenario 01 | integration | Un usuario Telegram puede usar operaciones financieras soportadas. |
| REQ-04 Scenario 02 | unit/integration | Se aplica timezone/default explícito cuando no hay teléfono. |
| REQ-05 Scenario 01 | integration | Telegram deshabilitado no afecta WhatsApp. |
| REQ-05 Scenario 02 | integration | Se rechazan requests con secreto inválido. |

### Implementation Risks

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Omisiones de queries todavía atadas a `whatsapp_number` | High | High | Hacer inventario explícito y cubrir regresión con tests de servicios clave. |
| Migración de `users.whatsapp_number` a nullable rompa expectativas en código legacy | Med | High | Refactorizar call sites principales en la misma feature y agregar tests de DB/modelos. |
| Duplicación accidental entre `chat_id` y `external_user_id` en Telegram | Med | Med | Definir claramente cuál ID es identidad de usuario y cuál es destinatario del canal. |
| Logs o errores expongan payloads completos de Telegram | Low | Med | Reusar patrones de logging sanitizado ya introducidos en feature 016. |

### Notes for sdd-spec-writer

La spec técnica debe dejar explícito que la compatibilidad con WhatsApp es un requisito de primer orden, no un efecto colateral. También conviene reflejar que el refactor multi-canal es la condición necesaria para que Telegram sea una integración real y no una adaptación superficial.
