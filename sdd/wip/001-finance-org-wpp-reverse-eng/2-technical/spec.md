# Technical Spec: Finance Org WPP Reverse Engineering

**Feature**: `001-finance-org-wpp-reverse-eng`
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-13
**Refs**: `1-functional/spec.md`

> **NOTA**: Esta spec fue generada por reverse engineering del código existente.
> Puede estar incompleta o imprecisa. Verificar contra el código fuente antes de usar como referencia.
> Generada el 2026-03-13 por sdd-reverse-engineer.

## Architecture Overview

La implementación observada sigue una arquitectura por capas liviana sobre FastAPI. El ingreso ocurre en `app/api/webhook.py`, que valida el webhook de Meta, parsea el payload y agenda el procesamiento en background. El mensaje luego pasa a `AgentLoop`, que construye contexto, obtiene personalidad persistida, expone herramientas al LLM y ejecuta un reasoning loop hasta obtener una respuesta final.

La solución usa dos persistencias distintas con responsabilidades separadas:
- Google Sheets como storage operativo de usuarios y gastos.
- PostgreSQL como storage relacional para usuarios, planes, grupos, metas y configuraciones de personalidad.

La memoria conversacional es in-memory por proceso y no es compartida entre instancias. La interacción externa depende de Meta WhatsApp Cloud API, Google Sheets API, proveedor LLM configurable y Groq para transcripción de audio.

```text
WhatsApp Cloud API
        |
        v
FastAPI /webhook
        |
        v
background task
        |
        v
AgentLoop
  |        |          |
  |        |          +--> ConversationMemory (in-memory TTL)
  |        |
  |        +--> ToolRegistry
  |               |--> SheetsService
  |               |--> currency/personality/goals/paywall helpers
  |               |--> WhatsApp outbound adapters
  |
  +--> LLMProvider (Gemini | DeepSeek)

PostgreSQL <--> user_service / personality / goals
Google Sheets <--> sheets.py
Groq Whisper <--> transcription.py
```

## Architecture Decision Records

### ADR-001: Orquestación de entrada por FastAPI con background tasks

- **Status**: Accepted
- **Context**: El webhook de Meta requiere respuestas HTTP rápidas y tolerantes a payloads incompletos.
- **Decision**: El endpoint `POST /webhook` responde siempre `{"status": "ok"}` y delega el procesamiento real a `BackgroundTasks`.
- **Consequences**: Reduce reintentos de Meta y desacopla la latencia del agente del ciclo HTTP. A cambio, el manejo de errores ocurre fuera de la respuesta HTTP y requiere logging para observabilidad.
- **Alternatives considered**: Procesamiento inline del mensaje dentro del request. No es el patrón observado.

### ADR-002: Agente LLM con tool calling como núcleo de dominio

- **Status**: Accepted
- **Context**: El bot debe resolver múltiples intenciones sin un router rígido por palabras clave.
- **Decision**: `app/agent/core.py` implementa un reasoning loop con `chat_with_tools`, `ToolRegistry` y un máximo de iteraciones configurable.
- **Consequences**: El sistema gana flexibilidad para registrar gastos, consultar resúmenes, calcular montos y encadenar tools. A cambio, la calidad depende del prompt, del proveedor LLM y de la forma en que se serializan resultados de tools.
- **Alternatives considered**: Routing determinístico previo al LLM. La documentación lo menciona como pasado, pero no es el mecanismo vigente.

### ADR-003: Persistencia híbrida entre Google Sheets y PostgreSQL

- **Status**: Accepted
- **Context**: El producto necesita registrar gastos de manera simple y también guardar configuración relacional como plan, grupos y personalidad.
- **Decision**: Los gastos viven en Google Sheets por usuario; la metadata relacional vive en PostgreSQL con SQLAlchemy async y migraciones Alembic.
- **Consequences**: La planilla sigue siendo el sistema visible para el usuario, mientras que datos estructurados como `plan` o `Goal` usan DB formal. A cambio, el dominio queda repartido entre dos fuentes de verdad con consistencia eventual manual.
- **Alternatives considered**: Unificar todo en Sheets o todo en DB. Ninguna de esas opciones aparece implementada hoy.

### ADR-004: Memoria conversacional efímera por proceso

- **Status**: Accepted
- **Context**: El agente necesita contexto reciente y soporte para replies nativos sin introducir infraestructura adicional.
- **Decision**: `ConversationMemory` usa diccionarios en memoria con TTL y un índice adicional `wamid -> texto`.
- **Consequences**: La implementación es simple y suficiente para una sola instancia. Se pierde estado al reiniciar proceso y no escala horizontalmente sin una capa compartida.
- **Alternatives considered**: Redis u otro backend compartido. La documentación lo menciona como posibilidad futura, pero no existe en código.

## Component Design

### Webhook API

**Responsabilidad**: Recibir eventos de WhatsApp, verificar el webhook, filtrar mensajes elegibles y disparar procesamiento asincrónico.

**Interfaz pública**:
```python
@router.get("/webhook")
async def verify_webhook(...)

@router.post("/webhook")
async def receive_message(request: Request, background_tasks: BackgroundTasks)
```

**Dependencias**: `settings`, `whatsapp`, `transcription`, `user_service`, `paywall`, `AgentLoop`.

### AgentLoop

**Responsabilidad**: Ejecutar el ciclo de decisión del agente, combinar historial, prompt base, personalidad persistida y resultados de tools.

**Interfaz pública**:
```python
class AgentLoop:
    async def process(
        self,
        phone: str,
        user_text: str,
        replied_to_id: str | None = None,
    ) -> str: ...
```

**Dependencias**: `ConversationMemory`, `ToolRegistry`, `LLMProvider`, `SheetsService`, `get_custom_prompt`.

**Observaciones**:
- Limpia tags `<think>` antes de responder o persistir.
- Convierte formatos de Markdown básico hacia un formato más compatible con WhatsApp.
- Intenta `ensure_user` en Sheets al comienzo del procesamiento si el servicio está disponible.

### ConversationMemory

**Responsabilidad**: Mantener historial temporal por teléfono e indexar mensajes salientes por `wamid`.

**Interfaz pública**:
```python
class ConversationMemory:
    def get(self, phone: str) -> list[Message]: ...
    def append(self, phone: str, messages: list[Message]) -> None: ...
    def clear(self, phone: str) -> None: ...
    def store_wamid(self, phone: str, wamid: str, text: str) -> None: ...
    def get_by_wamid(self, phone: str, wamid: str) -> str | None: ...
```

**Dependencias**: `datetime`, `Message`.

### ToolRegistry

**Responsabilidad**: Exponer al LLM el catálogo de herramientas y ejecutar la lógica de cada una.

**Interfaz pública**:
```python
class ToolRegistry:
    def definitions(self) -> list[ToolDefinition]: ...
    def run(self, name: str, **kwargs) -> dict: ...
```

**Dependencias**: `SheetsService`, `ParsedExpense`, `currency`, `goals`, `personality`, `whatsapp`, `httpx`, acceso async a DB.

**Tools observadas**:
- `register_expense`
- `get_monthly_summary`
- `get_category_breakdown`
- `get_recent_expenses`
- `delete_last_expense`
- `search_expenses`
- `get_sheet_url`
- `calculate`
- `convert_currency`
- `send_cat_pic`
- `get_user_groups_info`
- `save_personality`

### LLM Provider Abstraction

**Responsabilidad**: Uniformar interacción con Gemini y DeepSeek/OpenAI-compatible.

**Interfaz pública**:
```python
class LLMProvider(Protocol):
    async def complete(self, system_prompt: str, user_message: str) -> str: ...
    async def chat_with_tools(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
        system_prompt: str,
    ) -> ChatResponse: ...
```

**Dependencias**: `google.genai`, `httpx`, modelos `Message`, `ToolCall`, `ToolDefinition`, `ChatResponse`.

**Observaciones**:
- Gemini usa conversiones propias a `contents` y `function_response`.
- DeepSeek usa formato tipo OpenAI con `tool_calls`.

### SheetsService

**Responsabilidad**: Gestionar la planilla principal, la hoja `Usuarios` y las hojas de gastos por teléfono.

**Interfaz pública**:
```python
class SheetsService:
    def ensure_user(self, phone: str) -> bool: ...
    def append_expense(self, phone: str, expense: ParsedExpense) -> int: ...
    def delete_expense(self, phone: str, row_index: int) -> bool: ...
    def search_expenses(... ) -> list[dict]: ...
    def get_monthly_total(self, phone: str, month: int, year: int) -> float: ...
    def get_category_totals(self, phone: str, month: int, year: int) -> dict[str, float]: ...
    def get_recent_expenses(self, phone: str, n: int = 10) -> list[dict]: ...
    def get_sheet_url(self) -> str: ...
```

**Dependencias**: `gspread`, `google.oauth2.service_account`, `settings`, `ParsedExpense`.

### Relational Services

**Responsabilidad**: Operaciones de soporte en PostgreSQL.

**Componentes**:
- `user_service.get_or_create_user`: alta idempotente por `whatsapp_number`.
- `paywall.py`: validación de límites por plan.
- `goals.py`: actualización de metas activas y cierre por cumplimiento.
- `personality.py`: generar, guardar y recuperar prompts persistentes.

### WhatsApp and Media Adapters

**Responsabilidad**: envío de texto/imágenes y descarga de media desde Meta, más transcripción de audio.

**Interfaz pública**:
```python
async def send_text(phone_number: str, message: str) -> str | None: ...
def send_image_sync(phone_number: str, image_url: str) -> str | None: ...
async def download_media(media_id: str) -> bytes | None: ...
async def transcribe_audio(audio_bytes: bytes) -> str: ...
```

**Dependencias**: `httpx`, Graph API de Meta, API de Groq.

## Data Model

### Dominio relacional observado

```python
class User:
    id: int
    whatsapp_number: str
    plan: str  # FREE | PREMIUM en la lógica observada
    created_at: datetime

class Group:
    id: int
    whatsapp_group_id: str
    name: str
    created_at: datetime

class GroupMember:
    id: int
    user_id: int
    group_id: int
    role: str
    joined_at: datetime

class Goal:
    id: int
    user_id: int | None
    group_id: int | None
    target_amount: float
    current_amount: float
    status: str

class ChatConfiguration:
    id: int
    user_id: int | None
    group_id: int | None
    custom_prompt: str | None
```

### Modelo operativo en Google Sheets

Hoja `Usuarios`:
```text
Teléfono | Nombre | Moneda Default | Fecha Registro
```

Hoja `Gastos_{phone}`:
```text
Fecha | Hora | Monto | Moneda | Descripción | Categoría | Cálculo | Mensaje Original | Monto Original | Moneda Original
```

## API Contract

### `GET /webhook`

**Uso**: verificación inicial del webhook de Meta.

**Query params**:
- `hub.mode`
- `hub.challenge`
- `hub.verify_token`

**Respuesta exitosa**:
```text
challenge original
```

**Respuesta de error**:
- `403` si el token no coincide.

### `POST /webhook`

**Uso**: recepción de eventos de mensajes de WhatsApp.

**Entrada relevante observada**:
```json
{
  "entry": [
    {
      "changes": [
        {
          "value": {
            "messages": [
              {
                "from": "5491112345678",
                "type": "text|audio|image",
                "text": {"body": "Hola"},
                "audio": {"id": "media_id"},
                "image": {"id": "media_id"},
                "context": {"id": "wamid_referenciado"},
                "group_id": "grupo_opcional"
              }
            ]
          }
        }
      ]
    }
  ]
}
```

**Salida**:
```json
{"status":"ok"}
```

## Testing Strategy Observed

Los tests existentes combinan unit tests, integración liviana y e2e sintético con mocks.

**Unit tests observados**:
- `tests/test_agent.py`
- `tests/test_agent_strip.py`
- `tests/test_tools.py`
- `tests/test_sheets.py`
- `tests/test_llm_provider.py`
- `tests/test_whatsapp.py`
- `tests/test_transcription.py`
- `tests/test_paywall.py`
- `tests/test_personality.py`
- `tests/test_goals.py`
- `tests/test_db_models.py`

**Integration/e2e observados**:
- `tests/integration/test_agent_loop.py`
- `tests/e2e/test_api.py`
- `tests/test_webhook.py`

**Cobertura funcional visible**:
- Verificación de webhook.
- Flujo del agente con stop/tool_use.
- Limpieza de tags `<think>`.
- Conversión de mensajes para providers LLM.
- Operaciones principales de Sheets.
- Restricciones de paywall.
- Descarga de media y transcripción.
- Persistencia y lectura de personalidad.

## Implementation Risks

| Riesgo | Probabilidad | Impacto | Mitigación observada o recomendada |
|--------|--------------|---------|------------------------------------|
| Memoria conversacional perdida al reiniciar proceso | High | Medium | Reemplazar por backend compartido si se requiere continuidad o varias instancias. |
| Dominio repartido entre Sheets y PostgreSQL | Medium | High | Mantener contratos claros de qué dato vive en cada storage. |
| Diferencias entre docs y código real | High | Medium | Tratar `sdd/` y tests como baseline vigente y revisar `openspec/` manualmente. |
| Features de grupos parcialmente cableadas | Medium | Medium | Validar manualmente flujos end-to-end antes de promocionarlas como estables. |
| Conversión de moneda con tasas hardcodeadas | High | Medium | Reemplazar por fuente externa si el dato debe ser confiable en producción. |

## Reverse Engineering Notes

- El repo contiene documentación de producto y arquitectura más amplia que el código real.
- La lógica de grupos existe en modelos, tests y algunas tools, pero el flujo completo de administración grupal no está expuesto por endpoints dedicados.
- La transcripción de audio está implementada; el procesamiento de imágenes no.
- El servicio de `send_cat_pic` implica acceso a internet desde el proceso de aplicación, aunque no hay cobertura end-to-end visible en tests.
