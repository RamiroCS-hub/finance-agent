# Arquitectura - Bot de WhatsApp para Gestión de Gastos (Agente)

## 1. Visión General

Bot de WhatsApp que actúa como un **agente conversacional** para gestión de gastos personales. El agente recibe mensajes de texto libre, mantiene historial de conversación por usuario, razona sobre la intención usando un LLM con tool calling nativo, y ejecuta herramientas reales (registrar gasto, consultar resúmenes, etc.) iterativamente hasta formular una respuesta final.

A diferencia de un chatbot lineal, el agente puede:
- Manejar conversaciones multi-turno con contexto persistente.
- Entender intenciones complejas sin routing por keywords.
- Encadenar múltiples herramientas en una sola respuesta.
- Pedir aclaraciones cuando el mensaje es ambiguo.
- Razonar sobre cálculos y responder preguntas analíticas sobre el historial de gastos.

---

## 2. Stack Tecnológico

| Componente | Tecnología | Justificación |
|---|---|---|
| Runtime | Python 3.11+ | Ecosistema maduro, async nativo |
| Framework HTTP | FastAPI | Async, rápido, ideal para webhooks |
| WhatsApp API | Meta Cloud API (WhatsApp Business) | API oficial, gratuita hasta 1000 conversaciones/mes |
| Almacenamiento | Google Sheets API v4 | Accesible, compartible, sin infraestructura propia |
| LLM (razonamiento + tools) | LLM intercambiable (Gemini / DeepSeek) | Gemini gratuito para dev; DeepSeek económico para prod. Ambos soportan function calling |
| Memoria conversacional | In-memory (dict con TTL) | Volumen bajo; suficiente para usuarios simultáneos esperados. Reemplazable por Redis sin cambios de interfaz |
| Moneda | Configurable (default única) | El usuario configura su moneda base; el agente detecta otra si se menciona explícitamente |
| Deploy | Railway / Render / VPS | Opciones simples con HTTPS incluido |

---

## 3. Diagrama de Arquitectura

```
┌─────────────┐     HTTPS POST      ┌────────────────────────────────────────┐
│  WhatsApp    │ ──────────────────> │  FastAPI Server                        │
│  (Usuario)   │ <────────────────── │  /webhook                              │
└─────────────┘   Respuesta JSON     │                                        │
                                     │  ┌──────────────────────────────────┐  │
                                     │  │          Agent Core              │  │
                                     │  │                                  │  │
                                     │  │  ┌────────────────────────────┐  │  │
                                     │  │  │  Conversation Memory        │  │  │
                                     │  │  │  (historial por usuario)    │  │  │
                                     │  │  └────────────────────────────┘  │  │     ┌──────────────┐
                                     │  │                                  │──┼────>│ LLM Provider │
                                     │  │  ┌────────────────────────────┐  │  │<────│ (Gemini /    │
                                     │  │  │     Reasoning Loop          │  │  │     │  DeepSeek)   │
                                     │  │  │  while finish != "stop":    │  │  │     └──────────────┘
                                     │  │  │    llm.chat_with_tools()   │  │  │
                                     │  │  │    → tool_calls? ejecutar  │  │  │
                                     │  │  │    → stop? responder       │  │  │
                                     │  │  └────────────────────────────┘  │  │
                                     │  │                                  │  │
                                     │  │  ┌────────────────────────────┐  │  │
                                     │  │  │      Tool Registry          │  │  │
                                     │  │  │  register_expense          │  │  │
                                     │  │  │  get_monthly_summary        │  │  │
                                     │  │  │  get_category_breakdown     │  │  │
                                     │  │  │  get_recent_expenses        │  │  │
                                     │  │  │  delete_last_expense        │  │  │
                                     │  │  │  search_expenses            │  │  │
                                     │  │  │  get_sheet_url              │  │  │
                                     │  │  └────────────────────────────┘  │  │
                                     │  └──────────────────────────────────┘  │
                                     └──────────────────┬─────────────────────┘
                                                        │
                                              ┌─────────▼──────────┐
                                              │   Sheets Service    │
                                              │   (sin cambios)     │
                                              └─────────┬──────────┘
                                                        │
                                              ┌─────────▼──────────┐
                                              │   Google Sheets     │
                                              │   (spreadsheet del  │
                                              │    usuario)         │
                                              └────────────────────┘
```

---

## 4. Componentes Principales

### 4.1 Webhook Receiver (`app/api/webhook.py`)

Sin cambios funcionales respecto al diseño anterior. En el `POST /webhook`, en lugar de llamar a `router.route_message()`, ahora llama a `agent.process_message(phone, text)`.

- `GET /webhook` — Verificación del webhook (challenge de Meta).
- `POST /webhook` — Extrae `phone` y `text` del payload, valida firma y whitelist, delega al Agent Core.

### 4.2 Agent Core (`app/agent/core.py`)

Núcleo del agente. Implementa el **reasoning loop**: recibe el mensaje del usuario, recupera el historial de conversación, ejecuta el LLM con las herramientas disponibles e itera hasta que el LLM decide que tiene una respuesta final.

```
AgentLoop.process(phone, user_text)
    │
    ▼
memory.get(phone)  →  historial previo + nuevo mensaje de usuario
    │
    ▼
┌──────────────────────────────────────────┐
│  while True:                             │
│                                          │
│    response = llm.chat_with_tools(       │
│        messages,                         │
│        tools=tool_registry.definitions() │
│    )                                     │
│                                          │
│    if response.finish_reason == "stop":  │
│        break  ← respuesta final          │
│                                          │
│    for tool_call in response.tool_calls: │
│        result = tool_registry.run(       │
│            tool_call.name,               │
│            **tool_call.arguments         │
│        )                                 │
│        messages.append(tool_result)      │
└──────────────────────────────────────────┘
    │
    ▼
memory.append(phone, messages_actualizados)
    │
    ▼
whatsapp.send_text(phone, response.content)
```

**Límite de iteraciones**: `MAX_AGENT_ITERATIONS` (configurable, default 10) para evitar loops infinitos ante errores de herramienta.

### 4.3 Tool Registry (`app/agent/tools.py`)

Registro centralizado de todas las herramientas disponibles para el agente. Cada herramienta tiene:
- Nombre único.
- Descripción (la lee el LLM para decidir cuándo usarla).
- Esquema JSON de parámetros de entrada.
- Función Python que ejecuta la lógica.

#### Herramientas disponibles

| Herramienta | Descripción | Parámetros |
|---|---|---|
| `register_expense` | Registra un gasto en Google Sheets | `amount: float`, `description: str`, `category: str`, `currency: str` |
| `get_monthly_summary` | Resumen total y por categoría del mes | `month?: int`, `year?: int` |
| `get_category_breakdown` | Desglose detallado de una o todas las categorías | `month?: int`, `year?: int`, `category?: str` |
| `get_recent_expenses` | Lista los últimos N gastos | `limit?: int` (default 10) |
| `delete_last_expense` | Elimina el último gasto registrado por el usuario | — |
| `search_expenses` | Busca gastos por descripción o rango de fechas | `query?: str`, `date_from?: str`, `date_to?: str` |
| `get_sheet_url` | Devuelve el link al spreadsheet del usuario | — |

#### Definición de herramienta (ejemplo)

```python
ToolDefinition(
    name="register_expense",
    description=(
        "Registra un gasto del usuario en Google Sheets. "
        "Resuelve cualquier cálculo matemático antes de llamar esta herramienta. "
        "Usa la moneda por defecto del usuario a menos que el usuario especifique otra."
    ),
    parameters={
        "type": "object",
        "properties": {
            "amount":      {"type": "number",  "description": "Monto final ya calculado"},
            "description": {"type": "string",  "description": "Descripción del gasto"},
            "category":    {"type": "string",  "enum": CATEGORIES},
            "currency":    {"type": "string",  "description": "Código ISO 4217, ej: ARS, USD"},
        },
        "required": ["amount", "description", "category", "currency"],
    },
    fn=sheets_service.append_expense,
)
```

### 4.4 Conversation Memory (`app/agent/memory.py`)

Almacena el historial de mensajes por usuario para mantener contexto entre turnos de conversación.

```python
class ConversationMemory:
    def get(self, phone: str) -> list[Message]
        """Devuelve el historial del usuario. Lista vacía si no existe o expiró."""

    def append(self, phone: str, messages: list[Message]) -> None
        """Reemplaza el historial del usuario con la versión actualizada. Renueva el TTL."""

    def clear(self, phone: str) -> None
        """Borra el historial (el usuario puede pedir 'nueva conversación')."""
```

- Almacenamiento: `dict[phone → (messages, last_activity_ts)]` en memoria del proceso.
- TTL: `CONVERSATION_TTL_MINUTES` (default 60). Si el usuario no escribe en ese tiempo, el historial expira y la próxima conversación empieza limpia.
- Cada entrada en `messages` es un objeto `Message` con `role` (`user` | `assistant` | `tool`) y `content`.

> **Nota de escalabilidad**: la interfaz de `ConversationMemory` es intercambiable. Si el volumen crece, se puede reemplazar el backend in-memory por Redis sin modificar el Agent Core.

### 4.5 LLM Provider (`app/services/llm_provider.py`)

Capa de abstracción sobre el proveedor de LLM. Se extiende para soportar **tool calling nativo** (function calling en Gemini, tool use en DeepSeek/OpenAI-compatible).

La interfaz anterior (`complete(system_prompt, user_message) -> str`) se reemplaza por:

```python
class LLMProvider(Protocol):
    async def chat_with_tools(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
        system_prompt: str,
    ) -> ChatResponse: ...


@dataclass
class ChatResponse:
    content: str | None            # Texto de respuesta final (cuando finish_reason == "stop")
    tool_calls: list[ToolCall] | None  # Herramientas a ejecutar (cuando finish_reason == "tool_use")
    finish_reason: Literal["stop", "tool_use"]


@dataclass
class ToolCall:
    id: str           # Identificador único del call (requerido por algunos providers)
    name: str         # Nombre de la herramienta
    arguments: dict   # Argumentos parseados como dict


class GeminiProvider(LLMProvider):
    """Google AI Studio — Tier gratuito (15 RPM, 1M tokens/min). Usa function calling."""

class DeepSeekProvider(LLMProvider):
    """DeepSeek API — Económico para producción. API compatible con OpenAI tool calling."""
```

| Proveedor | Uso | Costo | Límite free tier |
|---|---|---|---|
| **Gemini 2.0 Flash** | Desarrollo y testing | Gratis | 15 req/min, 1M tokens/min |
| **DeepSeek Chat** | Producción | ~$0.14/M input, ~$0.28/M output | — |

#### System Prompt del Agente

El LLM recibe un system prompt que define su rol y restricciones:

```
Eres un asistente de finanzas personales accesible por WhatsApp.
Ayudas a registrar gastos, consultar resúmenes y analizar patrones de gasto.

- La moneda por defecto del usuario es {DEFAULT_CURRENCY}.
- La fecha de hoy es {current_date}.
- Responde siempre en español, de forma concisa y en formato WhatsApp
  (negrita con *asteriscos*, sin markdown adicional).
- Cuando registres un gasto, resuelve cualquier cálculo matemático
  antes de llamar la herramienta.
- Si el mensaje es ambiguo, pregunta para aclarar antes de registrar.
- No inventes datos: si no tienes la información, usa una herramienta.
```

#### Categorías disponibles

```python
CATEGORIES = [
    "Comida",
    "Transporte",
    "Supermercado",
    "Servicios",
    "Entretenimiento",
    "Salud",
    "Ropa",
    "Educación",
    "Hogar",
    "Otros",
]
```

### 4.6 Google Sheets Service (`app/services/sheets.py`)

Sin cambios estructurales respecto al diseño anterior. Las operaciones CRUD permanecen iguales; ahora son llamadas por las herramientas del Tool Registry en lugar de por handlers directos.

**Estructura del spreadsheet (multi-usuario):**

Hoja: `Usuarios`

| Columna A | B | C | D |
|---|---|---|---|
| Teléfono | Nombre | Moneda Default | Fecha Registro |

Hoja: `Gastos_{teléfono}` — una por usuario

| Columna A | B | C | D | E | F | G |
|---|---|---|---|---|---|---|
| Fecha | Hora | Monto | Moneda | Descripción | Categoría | Mensaje Original |

```python
class SheetsService:
    def ensure_user(self, phone: str) -> bool
    def append_expense(self, phone: str, expense: ParsedExpense) -> str  # retorna ID de fila
    def delete_expense(self, phone: str, row_id: str) -> bool
    def get_expenses_range(self, phone: str, start_date, end_date) -> list[dict]
    def get_monthly_total(self, phone: str, month: int, year: int) -> float
    def get_category_totals(self, phone: str, month: int, year: int) -> dict[str, float]
    def get_recent_expenses(self, phone: str, n: int = 10) -> list[dict]
    def search_expenses(self, phone: str, query: str, date_from=None, date_to=None) -> list[dict]
    def get_sheet_url(self) -> str
```

### 4.7 WhatsApp Sender (`app/services/whatsapp.py`)

Sin cambios. Envía mensajes de respuesta via Meta Cloud API.

```python
class WhatsAppSender:
    def send_text(self, phone_number: str, message: str) -> bool
    def send_template(self, phone_number: str, template: str, params: list) -> bool
```

---

## 5. Modelos de Datos (`app/models/`)

### `expense.py` — Resultado de registro de gasto

```python
@dataclass
class ParsedExpense:
    amount: float
    description: str
    category: str
    currency: str
    raw_message: str
```

### `agent.py` — Tipos del loop del agente

```python
@dataclass
class Message:
    role: Literal["system", "user", "assistant", "tool"]
    content: str | list  # str para texto, list para tool calls/results (formato provider-específico)

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict

@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict   # JSON Schema
    fn: Callable

@dataclass
class ChatResponse:
    content: str | None
    tool_calls: list[ToolCall] | None
    finish_reason: Literal["stop", "tool_use"]
```

---

## 6. Estructura de Directorios

```
finance_org_wpp/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app + startup + inyección de dependencias
│   ├── config.py                # Settings desde env vars
│   ├── api/
│   │   ├── __init__.py
│   │   └── webhook.py           # Endpoints GET/POST /webhook → llama a AgentLoop
│   ├── agent/                   # Núcleo del agente (NUEVO)
│   │   ├── __init__.py
│   │   ├── core.py              # AgentLoop: reasoning loop + orquestación
│   │   ├── tools.py             # ToolRegistry + definiciones de herramientas
│   │   └── memory.py            # ConversationMemory por usuario (in-memory + TTL)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── llm_provider.py      # GeminiProvider + DeepSeekProvider con tool calling
│   │   ├── sheets.py            # Google Sheets CRUD
│   │   └── whatsapp.py          # Envío de mensajes WhatsApp
│   └── models/
│       ├── __init__.py
│       ├── expense.py           # ParsedExpense
│       └── agent.py             # Message, ToolCall, ToolDefinition, ChatResponse
├── tests/
│   ├── test_agent.py            # Tests del reasoning loop (mocks de LLM y tools)
│   ├── test_tools.py            # Tests de cada herramienta individualmente
│   └── test_sheets.py          # Tests de integración con Google Sheets
├── credentials/
│   └── .gitkeep
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

**Eliminado** respecto al diseño anterior: `app/services/parser.py`, `app/services/router.py`, `app/handlers/` (expense.py, query.py, help.py). Su funcionalidad queda absorbida por el agente, las herramientas y el system prompt.

---

## 7. Configuración y Secrets

Variables de entorno (`.env`):

```env
# WhatsApp Meta Cloud API
WHATSAPP_TOKEN=<token de acceso permanente>
WHATSAPP_PHONE_NUMBER_ID=<ID del número de teléfono>
WHATSAPP_VERIFY_TOKEN=<token custom para verificar webhook>

# Google Sheets
GOOGLE_SHEETS_CREDENTIALS_PATH=credentials/service_account.json
GOOGLE_SPREADSHEET_ID=<ID del spreadsheet>

# LLM (proveedor intercambiable, ambos con soporte de tool calling)
LLM_PROVIDER=gemini                # "gemini" para dev (gratis), "deepseek" para prod
GEMINI_API_KEY=<api key de Google AI Studio>
GEMINI_MODEL=gemini-2.0-flash
DEEPSEEK_API_KEY=<api key de DeepSeek>
DEEPSEEK_MODEL=deepseek-chat

# Agente
DEFAULT_CURRENCY=ARS               # moneda por defecto (ISO 4217)
CONVERSATION_TTL_MINUTES=60        # tiempo de vida del historial conversacional
MAX_AGENT_ITERATIONS=10            # límite de iteraciones del reasoning loop

# App
ALLOWED_PHONE_NUMBERS=             # vacío = cualquiera puede usar el bot
LLM_TIMEOUT_SECONDS=10             # timeout por llamada al LLM
LOG_LEVEL=INFO
```

---

## 8. Flujos Principales

### 8.1 Registro de Gasto Simple

```
Usuario: "850 farmacia"
    │
    ▼
Webhook → AgentLoop.process("549...", "850 farmacia")
    │
    ▼
memory.get() → [] (historial vacío o expirado)
    │
    ▼
LLM recibe: [user: "850 farmacia"] + tools disponibles
LLM responde: tool_use → register_expense(amount=850, description="farmacia", category="Salud", currency="ARS")
    │
    ▼
tool_registry.run("register_expense", ...) → SheetsService.append_expense()
    │
    ▼
LLM recibe resultado de la herramienta → genera respuesta final
    │
    ▼
WhatsApp ← "✅ Registrado: *$850 ARS* — Farmacia _(Salud)_"
```

### 8.2 Registro con Cálculo Complejo

```
Usuario: "10 USD menos 22% de IVA"
    │
    ▼
LLM razona: 10 - (10 × 0.22) = 7.80
LLM responde: tool_use → register_expense(amount=7.80, description="compra", category="Otros", currency="USD")
    │
    ▼
tool_registry.run(...) → SheetsService.append_expense()
    │
    ▼
WhatsApp ← "✅ Registrado: *$7.80 USD* — Compra _(Otros)_
            Cálculo: 10 − 22% = 7.80"
```

### 8.3 Consulta Simple

```
Usuario: "resumen"
    │
    ▼
LLM responde: tool_use → get_monthly_summary() (infiere mes y año del system prompt)
    │
    ▼
tool devuelve: { total: 45300, categories: {...} }
    │
    ▼
LLM genera respuesta formateada:
    │
    ▼
WhatsApp ← "*Resumen Febrero 2026*
            Total: $45.300
            ─────────────
            🛒 Supermercado: $15.100 (33%)
            🍔 Comida: $12.500 (28%)
            🚗 Transporte: $8.200 (18%)
            ..."
```

### 8.4 Conversación Multi-turno

```
Usuario: "resumen"
AgentLoop → get_monthly_summary() → respuesta con totales de febrero

Usuario: "¿y el mes pasado?"
    │
    ▼
memory.get() → historial incluye el turno anterior
LLM infiere del contexto: mes pasado = enero 2026
LLM responde: tool_use → get_monthly_summary(month=1, year=2026)
    │
    ▼
WhatsApp ← "*Resumen Enero 2026*..."

Usuario: "¿en qué categoría gasté más en los dos meses?"
    │
    ▼
LLM razona con los resultados ya en el historial → responde sin llamar más tools
WhatsApp ← "En ambos meses gastaste más en *Supermercado*..."
```

### 8.5 Mensaje Ambiguo (el agente pide aclaración)

```
Usuario: "500"
    │
    ▼
LLM no puede determinar descripción ni categoría
LLM responde directamente (sin tool_use):
    │
    ▼
WhatsApp ← "¿En qué fue ese gasto de $500?"

Usuario: "el almuerzo"
    │
    ▼
LLM tiene contexto: registrar 500 ARS en almuerzo
LLM responde: tool_use → register_expense(amount=500, description="almuerzo", category="Comida", currency="ARS")
    │
    ▼
WhatsApp ← "✅ Registrado: *$500 ARS* — Almuerzo _(Comida)_"
```

### 8.6 Consulta Analítica Compleja

```
Usuario: "¿en qué gasté más esta semana comparado con la semana pasada?"
    │
    ▼
LLM razona: necesita datos de dos semanas → dos llamadas a herramientas
tool_use → search_expenses(date_from="2026-02-09", date_to="2026-02-15")
tool_use → search_expenses(date_from="2026-02-16", date_to="2026-02-19")
    │
    ▼
LLM analiza ambos resultados y genera comparativa
    │
    ▼
WhatsApp ← "Esta semana gastaste *$18.200* vs *$12.500* la semana pasada (+46%).
            El mayor aumento fue en Comida: +$3.800."
```

---

## 9. Seguridad

- **Validación de firma**: Verificar `X-Hub-Signature-256` en cada request entrante.
- **Whitelist de números**: Solo procesar mensajes de números autorizados (`ALLOWED_PHONE_NUMBERS`).
- **Service Account**: Credenciales de Google con scope mínimo (`spreadsheets` solamente).
- **Rate limiting**: Limitar requests por número para evitar abuso (ej: max 100 mensajes/hora).
- **Límite de iteraciones del agente**: `MAX_AGENT_ITERATIONS` previene loops de tool calls ante errores.
- **HTTPS obligatorio**: Meta Cloud API requiere HTTPS para el webhook.
- **TTL del historial**: La expiración automática limita la superficie de datos en memoria.

---

## 10. Escalabilidad Futura (fuera de scope inicial)

- **Backend de memoria Redis**: Reemplazar `ConversationMemory` in-memory por Redis sin cambiar la interfaz. Habilita múltiples instancias del servidor.
- **Presupuestos por categoría**: Nueva herramienta `set_budget` / `get_budget_status`; el agente alerta proactivamente cuando se acerca al límite.
- **Ingresos y balance**: Extender el esquema del spreadsheet y agregar herramientas `register_income` / `get_balance`.
- **Gastos recurrentes**: "todos los 1ro cobrame $5000 de alquiler" — scheduler + herramienta `add_recurring`.
- **Gráficos**: Herramienta `generate_chart` que produce imágenes con matplotlib y las envía por WhatsApp (mensajes de tipo `image`).
- **Exportar CSV/PDF**: Herramienta `export_expenses` por periodo.
- **Conversión de moneda**: Herramienta `convert_currency` integrada con una API de tipo de cambio.
- **Resumen semanal automático**: APScheduler que llama al agente con un mensaje sintético "genera resumen de la semana" para cada usuario activo.
- **Soporte multi-LLM adicional**: Agregar `ClaudeProvider` (Anthropic) a `llm_provider.py` si se requiere mayor capacidad de razonamiento.
