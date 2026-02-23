# Learnings — Lo que necesitás saber para entender este agente

Este documento es para un developer que quiere entender cómo funciona este bot de WhatsApp
con arquitectura de agente. No cubre Python básico ni programación general — se enfoca en
los conceptos de arquitectura, patrones y decisiones que hacen que todo funcione.

---

## 1. ¿Qué es un agente LLM?

Un agente LLM es un programa que usa un modelo de lenguaje como "cerebro" para tomar
decisiones. A diferencia de una llamada simple al LLM ("dame una respuesta"), un agente
puede **actuar**: ejecutar funciones, consultar bases de datos, llamar APIs, y luego
razonar sobre los resultados.

La diferencia clave con un chatbot tradicional:

| Chatbot tradicional | Agente LLM |
|---|---|
| Recibe texto → devuelve texto | Recibe texto → decide qué hacer → ejecuta → razona → responde |
| Flujo fijo (if/else, regex) | Flujo dinámico (el LLM decide) |
| No tiene herramientas | Tiene herramientas que puede usar |
| Respuesta en 1 paso | Puede iterar múltiples pasos |

En este proyecto, el agente recibe un mensaje como "850 farmacia" y decide por sí mismo
que tiene que llamar a `register_expense` con los argumentos correctos, ejecutar esa
función, y luego generar una respuesta amigable con el resultado.

---

## 2. El Reasoning Loop (el corazón del agente)

El patrón central de cualquier agente LLM es el **reasoning loop** (o **ReAct loop**:
Reasoning + Acting). Es un ciclo iterativo:

```
                    ┌──────────────────────────┐
                    │     LLM recibe:          │
                    │  - Historial de mensajes │
                    │  - Herramientas          │
                    │  - System prompt         │
                    └─────────┬────────────────┘
                              │
                    ┌─────────▼────────────────┐
                    │   LLM decide:            │
                    │   ¿Responder o actuar?   │
                    └─────────┬────────────────┘
                              │
              ┌───────────────┼───────────────┐
              │                               │
    ┌─────────▼──────────┐          ┌─────────▼──────────┐
    │  finish_reason:    │          │  finish_reason:    │
    │  "stop"            │          │  "tool_use"        │
    │                    │          │                    │
    │  → Retorna texto   │          │  → Ejecuta tools   │
    │  → FIN             │          │  → Agrega resultado │
    └────────────────────┘          │    al historial    │
                                    │  → VUELVE AL LOOP  │
                                    └────────────────────┘
```

**¿Por qué es un loop?** Porque el agente puede necesitar múltiples pasos. Ejemplo:

1. Usuario: "cuánto gasté en comida este mes"
2. LLM decide: usar `get_category_breakdown(category="Comida")`
3. Se ejecuta, resultado: `{"breakdown": {"Comida": 15000}}`
4. LLM recibe el resultado y **ahora sí responde**: "Gastaste $15.000 en comida este mes 🍔"

O más complejo:

1. Usuario: "200 + 300 + 400 + IVA en super"
2. LLM decide: usar `calculate("(200 + 300 + 400) * 1.21")`
3. Resultado: `{"result": 1089.0}`
4. LLM decide: usar `register_expense(amount=1089.0, description="super", category="Supermercado")`
5. Resultado: `{"success": true, "row_index": 5}`
6. LLM responde: "Registré $1.089 en supermercado (incluye 21% IVA)"

El loop tiene un **límite de iteraciones** (`MAX_AGENT_ITERATIONS = 10`) para evitar
loops infinitos si el LLM se confunde.

---

## 3. Tool Calling (Function Calling)

### ¿Qué es?

Tool calling es la capacidad de un LLM de **decidir cuándo y cómo invocar funciones**
en vez de responder con texto. No es el LLM ejecutando código — el LLM solo genera
un JSON estructurado diciendo "quiero llamar a esta función con estos argumentos", y
tu código la ejecuta.

### El flujo completo

```
1. Tu código le pasa al LLM:
   - El mensaje del usuario
   - Una lista de herramientas disponibles (nombre, descripción, JSON Schema de parámetros)

2. El LLM responde con UNA de dos cosas:
   a) Texto normal (finish_reason: "stop")
   b) Una o más tool calls (finish_reason: "tool_use"):
      { "name": "register_expense", "arguments": {"amount": 850, "description": "farmacia"} }

3. Tu código ejecuta la función y le devuelve el resultado al LLM

4. El LLM genera la respuesta final para el usuario
```

### Anatomía de una herramienta

Cada herramienta tiene 4 componentes:

```python
ToolDefinition(
    name="register_expense",              # Identificador único
    description="Registra un gasto...",    # El LLM lee esto para decidir cuándo usarla
    parameters={                           # JSON Schema: define qué argumentos acepta
        "type": "object",
        "properties": {
            "amount": {"type": "number", "description": "Monto del gasto"},
            "description": {"type": "string", "description": "Descripción breve"},
        },
        "required": ["amount", "description"],
    },
    fn=self._register_expense,             # La función Python real que se ejecuta
)
```

**La `description` es crítica.** Es lo que el LLM lee para decidir cuándo usar cada
herramienta. Una mala descripción = el LLM no la usa cuando debería, o la usa mal.

### JSON Schema

Los parámetros se definen con [JSON Schema](https://json-schema.org/), un estándar
para describir la estructura de datos JSON. Conceptos clave:

- `"type": "object"` → el input es un objeto con propiedades
- `"properties"` → define cada campo (nombre, tipo, descripción)
- `"required"` → campos obligatorios
- Tipos: `string`, `number`, `integer`, `boolean`, `array`, `object`

El LLM usa este schema para generar argumentos válidos. Si definís
`"amount": {"type": "number"}`, el LLM va a generar un número, no un string.

### Diferencias entre providers

Cada LLM provider implementa tool calling de forma distinta:

| Aspecto | Gemini | OpenAI / OpenRouter |
|---|---|---|
| Formato de tools | `FunctionDeclaration` + Schema propio | JSON Schema estándar en array `tools` |
| Tool calls en respuesta | `function_call` dentro de `parts` | `tool_calls` array con IDs |
| Tool results | `function_response` (role "user") | `role: "tool"` con `tool_call_id` |
| IDs únicos | No (usa el nombre de la función) | Sí (cada call tiene un ID único) |

Esto significa que cada provider necesita **convertir** entre el formato interno del
agente y el formato que espera el LLM. Esa conversión está en métodos como
`_messages_to_contents()` (Gemini) y `_messages_to_openai_format()` (DeepSeek).

---

## 4. Arquitectura de la aplicación

### Capas

```
┌─────────────────────────────────────────────┐
│  WhatsApp (Meta Cloud API)                  │
└──────────────────┬──────────────────────────┘
                   │ HTTP POST /webhook
┌──────────────────▼──────────────────────────┐
│  API Layer (FastAPI)                        │
│  app/api/webhook.py                         │
│  - Parsea payload de Meta                   │
│  - Valida whitelist                         │
│  - Delega al agente                         │
└──────────────────┬──────────────────────────┘
                   │ agent.process(phone, text)
┌──────────────────▼──────────────────────────┐
│  Agent Layer                                │
│  app/agent/core.py     → Reasoning loop     │
│  app/agent/tools.py    → Registro de tools  │
│  app/agent/memory.py   → Memoria por usuario│
└───────┬──────────────────────┬──────────────┘
        │                      │
┌───────▼───────┐    ┌─────────▼──────────────┐
│  LLM Provider │    │  Services              │
│  (Gemini o    │    │  sheets.py → Sheets    │
│   OpenRouter) │    │  whatsapp.py → Meta API│
└───────────────┘    └────────────────────────┘
```

### Principios de diseño

**Inversión de dependencias**: El `AgentLoop` no conoce qué LLM provider usa. Recibe
un `LLMProvider` (protocolo/interfaz) y lo usa. Cambiar de Gemini a DeepSeek es cambiar
una variable de entorno, no una línea de código.

**Separación de responsabilidades**:
- El webhook solo parsea y delega
- El agente solo orquesta (no sabe de HTTP ni de Sheets)
- Los tools solo ejecutan operaciones
- Los providers solo hablan con LLMs
- Los services solo hablan con APIs externas

**Fail-safe**: Si Google Sheets no está disponible, el bot arranca igual (con `sheets=None`).
Si una herramienta falla, el error se le pasa al LLM que genera una respuesta amigable.

---

## 5. System Prompt Engineering

El system prompt es **el contrato entre vos y el LLM**. Define cómo se comporta el
agente. No es un detalle menor — es parte central de la arquitectura.

### Estructura del prompt de este agente

```
1. ROL: "Sos un asistente de gestión de gastos personales para WhatsApp"
2. CONTEXTO: Fecha actual, moneda por defecto
3. COMPORTAMIENTO: Reglas de cuándo usar cada herramienta
4. REGLAS DE CÁLCULO: Cuándo y cómo usar calculate
5. REGLAS DE MÚLTIPLES GASTOS: Misma categoría, nombres como observación
6. FORMATO: Español, WhatsApp (negritas, emojis por categoría)
```

### Lecciones aprendidas

- **Sé explícito con ejemplos**: "22% iva 200" → `calculate("200 - 200 * 0.22")` funciona
  mucho mejor que "calculá el IVA". Los LLMs aprenden mejor de ejemplos que de instrucciones
  abstractas.

- **"NUNCA" funciona**: Decirle al LLM "NUNCA le pidas al usuario que calcule" evita que
  delegue la matemática al usuario.

- **El prompt es iterativo**: Se ajusta según el comportamiento real. Si el agente categoriza
  mal, se agregan reglas. Si confunde herramientas, se aclaran las descripciones.

- **Las herramientas compensan al prompt**: En vez de explicar cómo calcular en el prompt
  (el LLM puede equivocarse en la matemática), se creó una herramienta `calculate` que
  computa de forma exacta. El prompt solo dice "usá calculate".

---

## 6. Memoria Conversacional

### El problema

WhatsApp envía cada mensaje como un HTTP request independiente. Sin memoria, cada
mensaje sería una conversación nueva. El usuario no podría decir:

```
Usuario: "500 farmacia"
Bot: "Registrado ✅"
Usuario: "borralo"           ← ¿Borrar qué? Sin memoria no sabe.
```

### La solución

Un store en memoria indexado por número de teléfono con TTL (Time To Live):

```python
_store = {
    "5491123456789": (
        [Message(user, "500 farmacia"), Message(assistant, "Registrado ✅")],
        datetime(2026, 2, 20, 14, 30)  # última actividad
    )
}
```

- Cada mensaje nuevo recupera el historial y lo pasa al LLM
- Al terminar, se guarda el historial actualizado
- Después de 60 minutos sin actividad, se borra (TTL)

### Consideraciones de escalabilidad

La memoria actual es **in-memory** (un diccionario Python). Esto significa:
- Se pierde si el servidor se reinicia
- No escala a múltiples instancias
- Crece linealmente con usuarios activos

Para producción, se debería migrar a Redis o similar. La interfaz (`get`, `append`, `clear`)
está diseñada para que el cambio sea transparente.

---

## 7. Provider Pattern (Strategy Pattern)

### El problema

Queremos poder cambiar de LLM sin tocar el código del agente. Hoy usamos Gemini,
mañana podemos querer OpenRouter, Anthropic, o un modelo local.

### La solución

Un **protocolo** (interfaz) que define qué debe saber hacer un provider:

```python
class LLMProvider(Protocol):
    async def complete(self, system_prompt: str, user_message: str) -> str: ...
    async def chat_with_tools(self, messages, tools, system_prompt) -> ChatResponse: ...
```

Cada provider implementa esta interfaz a su manera:
- `GeminiProvider`: SDK de Google (`google.genai`)
- `DeepSeekProvider`: SDK de OpenRouter (`openrouter`)

Un factory selecciona el provider:

```python
def get_provider(config: Settings) -> LLMProvider:
    if config.LLM_PROVIDER == "gemini":
        return GeminiProvider(config)
    elif config.LLM_PROVIDER == "deepseek":
        return DeepSeekProvider(config)
```

Cambiar de provider = cambiar `LLM_PROVIDER=gemini` a `LLM_PROVIDER=deepseek` en `.env`.

### La complejidad escondida

Cada provider tiene que **traducir** entre el formato universal del agente y el formato
específico del LLM. Esta traducción tiene dos partes:

1. **Input**: Convertir `Message[]` y `ToolDefinition[]` al formato del provider
2. **Output**: Convertir la respuesta del provider a `ChatResponse`

Esto es el trabajo más tedioso del provider, pero es lo que permite que el agente sea
agnóstico del LLM.

---

## 8. Webhooks y la API de WhatsApp

### ¿Qué es un webhook?

Un webhook es una URL que registrás en un servicio externo (Meta, en este caso) para
que te envíe eventos en tiempo real. En vez de consultar "¿hay mensajes nuevos?" cada
X segundos (polling), Meta te avisa con un POST cuando llega un mensaje.

### El flujo de Meta WhatsApp Cloud API

```
1. SETUP (una vez):
   - Creás una app en developers.facebook.com
   - Configurás el webhook URL (tu servidor público)
   - Meta envía un GET con un challenge → tu servidor responde
   - Meta verifica que el webhook funciona

2. RUNTIME (cada mensaje):
   - Usuario envía mensaje por WhatsApp
   - Meta envía POST a tu webhook con el payload
   - Tu servidor procesa y responde
   - Tu servidor envía la respuesta via POST a la Graph API de Meta
```

### El payload de Meta

Meta envía un JSON anidado. La estructura relevante:

```json
{
  "entry": [{
    "changes": [{
      "value": {
        "messages": [{
          "from": "5491123456789",
          "type": "text",
          "text": { "body": "850 farmacia" }
        }]
      }
    }]
  }]
}
```

Hay que navegar `entry[0].changes[0].value.messages[0]` para llegar al mensaje.
No todos los webhooks traen mensajes (pueden ser status updates), por eso se verifica
`"messages" in value`.

### Ngrok para desarrollo

En desarrollo, tu servidor corre en `localhost:8080` — Meta no puede llegar ahí.
[ngrok](https://ngrok.com/) crea un túnel público:

```
Internet → https://xxx.ngrok-free.dev → localhost:8080
```

El `run.sh` levanta uvicorn + ngrok automáticamente.

---

## 9. Google Sheets como base de datos

### ¿Por qué Sheets?

Para un MVP/proyecto personal, Sheets tiene ventajas:
- Sin infraestructura (no hay que levantar un DB server)
- UI gratis para ver y editar datos
- API REST con SDK de Python (`gspread`)
- Compartible (el usuario puede ver su planilla)

### Estructura multi-usuario

```
Spreadsheet
├── Usuarios (hoja)
│   └── Teléfono | Nombre | Moneda | Fecha Registro
├── Gastos_5491123456789 (hoja por usuario)
│   └── Fecha | Hora | Monto | Moneda | Descripción | Categoría | ...
└── Gastos_5491187654321 (otro usuario)
    └── ...
```

Cada usuario tiene su propia hoja de gastos. `ensure_user()` crea la hoja automáticamente
la primera vez.

### Limitaciones

- **Velocidad**: Cada operación es un HTTP request a la API de Google (~200-500ms)
- **Concurrencia**: No soporta bien escrituras simultáneas al mismo rango
- **Escalabilidad**: Límite de 10M celdas por spreadsheet, rate limits de la API
- **Sin transacciones**: No hay rollback si falla a mitad de una operación

Para producción real, se migraría a PostgreSQL o similar.

---

## 10. Evaluación segura de expresiones (la tool `calculate`)

### El problema

El LLM no es confiable haciendo matemática. "200 - 200 * 0.22" puede dar resultados
incorrectos si el LLM intenta calcularlo internamente. Necesitamos una herramienta
que compute de forma exacta.

### ¿Por qué no usar `eval()`?

`eval("200 - 200 * 0.22")` funciona, pero `eval()` ejecuta **cualquier código Python**.
Un atacante podría enviar `"__import__('os').system('rm -rf /')"` y el servidor lo
ejecutaría. Nunca uses `eval()` con input del usuario (ni del LLM, que genera texto
a partir de input del usuario).

### La solución: AST parsing

Se usa el módulo `ast` de Python para parsear la expresión como un árbol sintáctico
y solo permitir operaciones aritméticas:

```
Expresión: "200 - 200 * 0.22"

AST:
    BinOp(-)
    ├── Constant(200)
    └── BinOp(*)
        ├── Constant(200)
        └── Constant(0.22)
```

Solo se permiten nodos de tipo `Constant`, `BinOp` y `UnaryOp` con operadores
aritméticos (`+`, `-`, `*`, `/`, `%`, `**`). Cualquier otra cosa (llamadas a funciones,
imports, acceso a atributos) lanza un error.

---

## 11. Elección de modelos

### Factores a considerar

No todos los modelos sirven para un agente con tool calling. Hay que evaluar:

| Factor | Por qué importa |
|---|---|
| **Soporte de tool calling** | Sin esto, el agente no funciona. Modelos de razonamiento (R1) generalmente no lo soportan. |
| **Cantidad de tools** | Más herramientas = modelo más grande necesario para elegir bien |
| **Idioma** | Modelos chicos pueden fallar con español coloquial ("10k uber") |
| **Consistencia** | ¿Categoriza "farmacia" como "Salud" siempre o a veces como "Otros"? |
| **Costo** | Modelos gratuitos tienen rate limits y menor calidad |
| **Latencia** | El usuario espera en WhatsApp — más de 10s es mala experiencia |

### Modelos probados en este proyecto

| Modelo | Tool calling | Calidad | Notas |
|---|---|---|---|
| Gemini 2.0 Flash | Sí | Buena | Tier gratuito generoso, buena latencia |
| DeepSeek V3 (free via OpenRouter) | Sí | Buena | Gratis, soporta tools |
| DeepSeek R1 (free via OpenRouter) | **No** | N/A | Modelo de razonamiento, no soporta tools |
| Gemma 3 27B (free via OpenRouter) | Sí | Regular | Inconsistente en categorización y formato |

### Lección clave

**"Free" no siempre significa "gratis y funciona"**. Un modelo gratis que no soporta
tool calling es inútil para un agente. Siempre verificá que el modelo soporte las
features que necesitás antes de integrarlo.

---

## 12. Testing de un agente LLM

### El desafío

Un agente tiene componentes determinísticos (tools, sheets) y no-determinísticos (LLM).
No podés testear contra el LLM real porque:
- Las respuestas varían entre ejecuciones
- Cuesta dinero/tokens
- Es lento
- Depende de disponibilidad del servicio

### La estrategia: mocks en cada capa

```
Tests de AgentLoop    → Mock del LLMProvider (respuestas predefinidas)
Tests de Tools        → Mock del SheetsService
Tests de LLMProvider  → Mock del SDK/HTTP (OpenRouter, Gemini)
Tests de Sheets       → Mock de gspread
```

Cada capa se testea con mocks de sus dependencias. Esto permite:
- Tests rápidos (~1 segundo total)
- Tests determinísticos (siempre pasan o fallan igual)
- Sin API keys ni servicios externos
- Cobertura del 100% de la lógica

### Qué NO se puede testear así

- Que el LLM realmente entienda "850 farmacia" como un gasto
- Que el LLM elija la herramienta correcta
- Que el system prompt funcione bien con un modelo nuevo

Para eso se necesitan **tests de integración** con el LLM real o **evaluaciones**
(evals) con datasets de mensajes y respuestas esperadas.
