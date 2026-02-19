# Plan de Desarrollo - Bot de WhatsApp para Gestión de Gastos (Agente)

## Estado general del proyecto

| Fase | Estado | Descripción |
|---|---|---|
| Fase 0 | ✅ | Setup de cuentas, proyecto y spreadsheet |
| Fase 1 | ✅ | Webhook recibe mensajes de WhatsApp |
| Fase 2 | 🔄 | LLM Provider con tool calling (refactoring) |
| Fase 3 | 🔄 | Sheets Service — extensión con delete y search |
| Fase 4 | ⬜ | Agent Core (memory, tools, reasoning loop) |
| Fase 5 | ⬜ | Limpieza: eliminar arquitectura vieja |
| Fase 6 | ⬜ | Tests del agente |
| Fase 7 | ⬜ | Deploy en producción con HTTPS |
| Fase 8 | ⬜ | Refinamiento y UX |

> ✅ Completado · 🔄 Refactoring de código existente · ⬜ Pendiente

---

## Fase 0: Setup Inicial ✅

### 0.1 Cuentas y Accesos — completado

- [x] App en Meta Developer Portal con producto WhatsApp activado.
- [x] Token de acceso, Phone Number ID y WhatsApp Business Account ID obtenidos.
- [x] Proyecto en Google Cloud Console con Google Sheets API habilitada.
- [x] Service Account con JSON de credenciales descargado.
- [x] Google Spreadsheet compartido con la service account (editor).

### 0.2 Proyecto Local — completado

Estructura del proyecto inicializada, dependencias instaladas, `.env` configurado.

### 0.3 Actualizar `.env.example` con nuevas variables del agente

Agregar al `.env.example` existente:

```env
# Agente
CONVERSATION_TTL_MINUTES=60
MAX_AGENT_ITERATIONS=10
```

---

## Fase 1: Webhook + Recepción de Mensajes ✅

Implementado. `GET /webhook` y `POST /webhook` funcionan.

**Ajuste pendiente** (se hará en Fase 4): el `POST /webhook` actualmente llama a `router.route_message()`. Pasará a llamar a `AgentLoop.process(phone, text)`.

---

## Fase 2: LLM Provider — Tool Calling 🔄

**Objetivo**: Extender `llm_provider.py` para que soporte el protocolo de tool calling nativo de cada proveedor.

### Contexto

El `llm_provider.py` actual expone solo `complete(system_prompt, user_message) -> str`. El agente necesita `chat_with_tools(messages, tools, system_prompt) -> ChatResponse` para poder recibir listas de mensajes y definiciones de herramientas.

### Tareas

1. **Crear `app/models/agent.py`**

   ```python
   from dataclasses import dataclass, field
   from typing import Literal, Callable, Any

   @dataclass
   class Message:
       role: Literal["system", "user", "assistant", "tool"]
       content: str | list  # str para texto; list para tool calls/results (formato provider-específico)

   @dataclass
   class ToolCall:
       id: str
       name: str
       arguments: dict

   @dataclass
   class ToolDefinition:
       name: str
       description: str
       parameters: dict   # JSON Schema del input
       fn: Callable

   @dataclass
   class ChatResponse:
       content: str | None
       tool_calls: list[ToolCall] | None
       finish_reason: Literal["stop", "tool_use"]
   ```

2. **Extender `app/services/llm_provider.py`**

   - Agregar método `chat_with_tools()` al protocolo `LLMProvider`.
   - Implementar en `GeminiProvider` usando la API de function calling de Google Generative AI.
   - Implementar en `DeepSeekProvider` usando el formato de tool calling compatible con OpenAI.
   - Mantener el método `complete()` existente mientras sea usado (se eliminará en Fase 5).

   ```python
   class LLMProvider(Protocol):
       async def complete(self, system_prompt: str, user_message: str) -> str: ...  # legacy
       async def chat_with_tools(
           self,
           messages: list[Message],
           tools: list[ToolDefinition],
           system_prompt: str,
       ) -> ChatResponse: ...
   ```

### Criterio de éxito

- Un test manual (o script) llama a `chat_with_tools` con un mensaje simple y una herramienta dummy.
- El LLM responde con `finish_reason="tool_use"` y un `ToolCall` con el nombre correcto.
- El LLM responde con `finish_reason="stop"` cuando no necesita herramientas.

---

## Fase 3: Google Sheets Service — Extensión 🔄

**Objetivo**: Agregar los dos métodos que necesita el Tool Registry pero no existen aún.

### Tareas

1. **Agregar `delete_expense(phone, row_index)` a `SheetsService`**
   - Elimina una fila por índice de la hoja `Gastos_{phone}`.
   - Para "borrar último gasto": obtener la última fila con `get_recent_expenses(n=1)` y borrar su índice.
   - Retorna `bool` indicando éxito.

2. **Agregar `search_expenses(phone, query?, date_from?, date_to?)` a `SheetsService`**
   - Filtra por texto en la columna Descripción (búsqueda case-insensitive).
   - Filtra por rango de fechas (columna Fecha en formato `YYYY-MM-DD`).
   - Retorna `list[dict]` con las filas que coinciden.

3. **Actualizar `append_expense` para retornar el índice de fila**
   - Actualmente retorna `bool`. Cambiar a `int` (índice de fila en el sheet) para que `delete_expense` pueda referenciarlo.

### Criterio de éxito

- `search_expenses(phone, query="uber")` devuelve solo los gastos de uber.
- `delete_expense(phone, last_row_index)` elimina la última fila y se puede verificar en el sheet.

---

## Fase 4: Agent Core ⬜

**Objetivo**: Construir el núcleo del agente: memoria de conversación, registro de herramientas y el reasoning loop.

### Tareas

1. **Crear `app/agent/memory.py`**

   ```python
   from datetime import datetime, timedelta
   from app.models.agent import Message

   class ConversationMemory:
       def __init__(self, ttl_minutes: int = 60):
           self._store: dict[str, tuple[list[Message], datetime]] = {}
           self._ttl = timedelta(minutes=ttl_minutes)

       def get(self, phone: str) -> list[Message]:
           """Devuelve historial del usuario. Lista vacía si no existe o expiró."""
           ...

       def append(self, phone: str, messages: list[Message]) -> None:
           """Reemplaza historial y renueva TTL."""
           ...

       def clear(self, phone: str) -> None:
           """Borra historial manualmente (ej: usuario pide 'nueva conversación')."""
           ...
   ```

2. **Crear `app/agent/tools.py`**

   - Definir las 7 herramientas con `ToolDefinition` (nombre, descripción, JSON Schema, función):
     - `register_expense(amount, description, category, currency)`
     - `get_monthly_summary(month?, year?)`
     - `get_category_breakdown(month?, year?, category?)`
     - `get_recent_expenses(limit?)`
     - `delete_last_expense()`
     - `search_expenses(query?, date_from?, date_to?)`
     - `get_sheet_url()`
   - Clase `ToolRegistry` con método `run(name, **kwargs)` que despacha a la función correcta.
   - Las funciones son wrappers delgados sobre `SheetsService`.

   ```python
   class ToolRegistry:
       def __init__(self, sheets: SheetsService, phone: str):
           ...  # el phone se pasa al crear el registry por request

       def definitions(self) -> list[ToolDefinition]:
           """Retorna todas las definiciones para pasarlas al LLM."""
           ...

       def run(self, name: str, **kwargs) -> dict:
           """Ejecuta la herramienta por nombre. Retorna dict serializable."""
           ...
   ```

3. **Crear `app/agent/core.py`**

   - Clase `AgentLoop` con método `process(phone, user_text) -> str`.
   - Instancia `ToolRegistry` con el `phone` del usuario.
   - Construye el system prompt con fecha actual y moneda por defecto.
   - Implementa el loop:

   ```python
   async def process(self, phone: str, user_text: str) -> str:
       messages = self.memory.get(phone) + [Message(role="user", content=user_text)]
       tools = ToolRegistry(self.sheets, phone)

       for _ in range(self.max_iterations):
           response = await self.llm.chat_with_tools(messages, tools.definitions(), SYSTEM_PROMPT)

           if response.finish_reason == "stop":
               messages.append(Message(role="assistant", content=response.content))
               self.memory.append(phone, messages)
               return response.content

           # tool_use: ejecutar herramientas y continuar
           messages.append(Message(role="assistant", content=response.tool_calls))
           for tool_call in response.tool_calls:
               result = tools.run(tool_call.name, **tool_call.arguments)
               messages.append(Message(role="tool", content=str(result)))

       # Si se agotaron las iteraciones
       self.memory.append(phone, messages)
       return "Hubo un problema procesando tu mensaje. Intentá de nuevo."
   ```

4. **Actualizar `app/main.py`**
   - Instanciar `ConversationMemory` y `AgentLoop` al arrancar.
   - Pasar `AgentLoop` al router del webhook via `init_dependencies`.

5. **Actualizar `app/config.py`**
   - Agregar `CONVERSATION_TTL_MINUTES: int = 60`
   - Agregar `MAX_AGENT_ITERATIONS: int = 10`

6. **Actualizar `app/api/webhook.py`**
   - En el handler `POST /webhook`, reemplazar la llamada a `route_message()` por `await agent.process(phone, text)`.

### Criterio de éxito

- Enviar "850 farmacia" → bot registra el gasto y responde con confirmación.
- Enviar "resumen" → bot llama `get_monthly_summary` y responde con datos reales.
- Enviar "500" (ambiguo) → bot pregunta "¿en qué fue ese gasto?", y en el siguiente mensaje registra con el monto y descripción combinados.
- Enviar "resumen" seguido de "¿y el mes pasado?" → bot responde con datos del mes anterior usando el contexto de la primera respuesta.

---

## Fase 5: Limpieza — Eliminar Arquitectura Vieja ⬜

**Objetivo**: Eliminar los archivos de la arquitectura anterior que quedaron obsoletos.

### Archivos a eliminar

- `app/services/parser.py`
- `app/services/router.py`
- `app/handlers/expense.py`
- `app/handlers/query.py`
- `app/handlers/help.py`
- `app/handlers/__init__.py`
- El directorio `app/handlers/` (si queda vacío)

### Verificar que `app/main.py` y `app/api/webhook.py` no importan estos módulos antes de eliminar.

### Criterio de éxito

- `python -c "from app.main import app"` no arroja `ImportError`.
- El bot sigue funcionando end-to-end después de la eliminación.

---

## Fase 6: Tests del Agente ⬜

**Objetivo**: Cubrir los componentes críticos del agente con tests.

### Tareas

1. **Crear `tests/test_agent.py`** — tests del `AgentLoop` con mocks

   - Mock del `LLMProvider` que simula respuestas con `tool_use` y `stop`.
   - Mock del `SheetsService`.
   - Test: mensaje de gasto simple → LLM llama `register_expense` → respuesta correcta.
   - Test: LLM devuelve `stop` directamente → respuesta sin tool calls.
   - Test: LLM llama una herramienta inválida → `AgentLoop` maneja el error sin crash.
   - Test: se alcanzan `MAX_AGENT_ITERATIONS` → retorna mensaje de error, no loop infinito.
   - Test: memoria expira (TTL) → próximo mensaje empieza con historial vacío.

2. **Crear `tests/test_tools.py`** — tests del `ToolRegistry`

   - Test: `register_expense` con parámetros válidos llama a `SheetsService.append_expense`.
   - Test: `get_monthly_summary` retorna dict con `total` y `categories`.
   - Test: `delete_last_expense` llama a `get_recent_expenses(n=1)` y luego `delete_expense`.
   - Test: herramienta con nombre desconocido lanza excepción controlada.

3. **Crear `tests/test_sheets.py`** — tests de integración con Google Sheets

   - Test con mock de `gspread` (o spreadsheet de testing).
   - Test: `append_expense` agrega fila y retorna índice.
   - Test: `search_expenses` filtra correctamente por query y fechas.
   - Test: `delete_expense` elimina la fila indicada.
   - Test: `get_monthly_total` suma correctamente los montos del mes.

### Criterio de éxito

- `pytest tests/` pasa sin errores.
- Cobertura del `AgentLoop` ≥ 80%.

---

## Fase 7: Deploy ⬜

**Objetivo**: Bot corriendo 24/7 accesible por HTTPS.

### Opción A: Railway (recomendada)

1. Crear cuenta en [Railway](https://railway.app/) y conectar el repo de GitHub.
2. Configurar variables de entorno en Railway dashboard (todas las del `.env`).
3. Subir credenciales de Google como variable `GOOGLE_CREDENTIALS_JSON` (base64 encoded) o como archivo adjunto.
4. Agregar `Procfile`:
   ```
   web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```
5. Deploy automático al pushear a `main`.
6. Configurar la URL de Railway como webhook en Meta Developer Portal.

### Opción B: Render

Similar a Railway. Web Service con el mismo `Procfile` o start command.

### Opción C: VPS

Ubuntu + nginx como reverse proxy + certbot para HTTPS + systemd o docker-compose.

### Post-deploy

- [ ] Configurar webhook URL definitiva en Meta.
- [ ] Verificar que el webhook responde correctamente.
- [ ] Solicitar verificación de la app en Meta (para salir del modo desarrollo).
- [ ] Generar token de acceso permanente (System User Token).

### Criterio de éxito

- El bot responde 24/7 sin intervención manual.

---

## Fase 8: Refinamiento y UX ⬜

**Objetivo**: Mejorar la experiencia de usuario aprovechando las capacidades del agente.

### Tareas

1. **Confirmación inteligente manejada por el LLM**
   - El agente pide confirmación ante montos inusualmente altos o mensajes ambiguos.
   - No requiere código extra: el system prompt instruye al agente cuándo pedir confirmación.

2. **Comando "nueva conversación"**
   - Si el usuario escribe "nueva conversación", "reset" o "empezar de nuevo" → llamar a `memory.clear(phone)`.
   - Agregar herramienta `clear_conversation()` para que el LLM pueda usarla si el usuario lo pide de forma indirecta.

3. **Manejo de errores amigable**
   - Si `SheetsService` lanza excepción → la herramienta retorna un dict de error.
   - El agente informa al usuario con un mensaje claro ("Hubo un problema guardando tu gasto...").

4. **Formato de montos y respuestas**
   - El system prompt instruye al agente a usar formato WhatsApp (`*negrita*`, `_cursiva_`).
   - Emojis por categoría en resúmenes.

5. **Resumen semanal automático (opcional)**
   - APScheduler o cron que llama a `AgentLoop.process(phone, "genera resumen de la semana")` para cada usuario activo.

---

## Dependencias (`requirements.txt`)

```
fastapi==0.115.0
uvicorn==0.32.0
httpx==0.27.0
gspread==6.1.0
google-auth==2.35.0
google-genai==1.5.0
python-dotenv==1.0.1
```

No se requieren dependencias nuevas: `google-genai` ya soporta function calling y `httpx` sirve para la API de DeepSeek.

---

## Riesgos y Mitigaciones

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Rate limit de Meta Cloud API | No se envían respuestas | Respetar límites (80 msgs/seg), retry con backoff |
| Rate limit de Google Sheets API | No se guardan gastos | Batch writes, cache local temporal |
| LLM en loop de tool calls | Bot colgado, costo de tokens | `MAX_AGENT_ITERATIONS` corta el loop; loggear y alertar |
| LLM llama herramienta con parámetros incorrectos | Error en tool → respuesta vacía | Validar parámetros en `ToolRegistry.run()` y retornar error estructurado al LLM |
| Cambios en formato de payload de Meta | Bot deja de funcionar | Loggear payloads raw, tests de integración |
| Token de WhatsApp expira | Bot deja de responder | System User Token (permanente), monitorear errores 401 |
| Crecimiento de memoria conversacional | Aumento de uso de RAM | TTL agresivo (60 min), migrar a Redis si supera 100 usuarios activos simultáneos |
