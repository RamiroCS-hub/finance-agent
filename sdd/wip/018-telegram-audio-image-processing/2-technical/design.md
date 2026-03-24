## Design Document

**Feature**: 018-telegram-audio-image-processing
**Diseñado por**: sdd-designer
**Fecha**: 2026-03-23

### Architecture Overview

La solución amplía `POST /telegram/webhook` para reconocer dos nuevos paths privados: audio (`voice`/`audio`) e imagen (`photo`). El webhook de Telegram deja de ser un simple filtro text-only y pasa a normalizar tres entradas soportadas: texto, audio e imagen. Para evitar una bifurcación funcional respecto de WhatsApp, la lógica de negocio de media privada se extrae a un helper compartido que ambos canales pueden invocar con un contexto común: usuario resuelto, tipo de media, MIME, bytes, caption opcional y funciones de salida.

```text
Telegram update
    -> validate secret + dedup
    -> classify message (text | audio | image | unsupported)
    -> resolve user context
    -> file metadata lookup + media policy validation
    -> download bytes
    -> shared private-media handler
         -> audio: transcribe -> AgentLoop.process(...)
         -> image: OCR -> register expense / ask for confirmation
    -> MessageDispatcher.send_text("telegram", chat_id, ...)
```

WhatsApp debe converger hacia el mismo helper compartido para audio e imágenes privadas, manteniendo sus validaciones específicas de entrada pero evitando duplicar OCR, transcripción, mensajes de error y persistencia financiera.

### ADRs

#### ADR-001: Extraer un flujo compartido de media privada

- **Context**: El pipeline completo de audio e imagen vive hoy dentro de `app/api/webhook.py`, acoplado a WhatsApp.
- **Decision**: Extraer la lógica común de transcripción, OCR, persistencia y mensajes de progreso/error a un helper/servicio compartido para media privada.
- **Consequences**: Reduce divergencia futura entre canales y hace viable Telegram media sin copiar cientos de líneas. Implica tocar `app/api/webhook.py` y revalidar regresión de WhatsApp.
- **Alternatives considered**: Duplicar el pipeline en `telegram_webhook.py`. Se descarta por deuda inmediata y alto riesgo de drift funcional.

#### ADR-002: Normalizar metadata y descarga de archivos de Telegram en el service del canal

- **Context**: Telegram entrega media mediante `file_id` y resolución posterior vía `getFile`, diferente a Meta.
- **Decision**: Extender `app/services/telegram.py` con helpers para resolver metadata mínima normalizada y descargar bytes, manteniendo fuera del webhook la lógica HTTP específica del proveedor.
- **Consequences**: El webhook queda más declarativo y testeable. El servicio de Telegram pasa a concentrar tanto salida como operaciones de archivo del canal.
- **Alternatives considered**: Resolver `getFile` y descargas inline en el webhook. Se descarta por mezcla de responsabilidades y tests más frágiles.

#### ADR-003: Policy de media explícita para Telegram, separada de WhatsApp

- **Context**: Los límites de WhatsApp ya existen, pero dependen de otra plataforma y no deben asumirse idénticos para Telegram.
- **Decision**: Agregar settings propios para tamaño y MIME permitidos de audio e imagen en Telegram.
- **Consequences**: La policy queda clara por canal y puede ajustarse sin efectos colaterales sobre Meta. Requiere documentación adicional y tests de configuración.
- **Alternatives considered**: Reutilizar las variables de WhatsApp. Se descarta por acoplamiento entre proveedores con semánticas distintas.

#### ADR-004: Mantener el aviso explícito para media fuera de alcance

- **Context**: El usuario ya pidió que el bot no silencie capacidades faltantes.
- **Decision**: Conservar y expandir el handler actual para que solo `voice`/`audio` y `photo` entren al pipeline nuevo; el resto de media privada debe responder con una limitación clara.
- **Consequences**: El comportamiento del canal sigue siendo honesto y gradual. La feature no se expande accidentalmente a documentos/video.
- **Alternatives considered**: Ignorar media fuera de alcance o aceptar todo lo descargable. Se descartan por mala UX y riesgo de abrir superficies no testeadas.

### Component Design

#### `app/services/telegram.py`

**Responsabilidad**: Encapsular la Bot API de Telegram para mensajes salientes, resolución de archivos y descarga de media.

**Interfaz pública**:
```python
async def send_text(chat_id: str, message: str) -> str | None: ...
async def get_file(file_id: str) -> dict | None: ...
async def get_media_metadata(message: dict) -> dict | None: ...
async def download_file(file_path: str) -> bytes | None: ...
```

**Dependencias**: `httpx`, settings de Telegram.

**Invariantes**:
- Los logs no exponen payloads completos ni IDs sensibles sin sanitización.
- La metadata normalizada siempre expresa `mime_type`, `file_size`, `file_id` y `file_path` cuando existan.

#### `app/api/telegram_webhook.py`

**Responsabilidad**: Clasificar updates privados, aplicar validaciones tempranas y delegar media soportada al pipeline compartido.

**Interfaz pública**:
```python
@router.post("/telegram/webhook")
async def receive_telegram_update(request: Request, background_tasks: BackgroundTasks): ...
```

**Dependencias**: `ChannelIdentityService`, `MessageDispatcher`, `AgentLoop`, service de Telegram, helper compartido de media.

**Invariantes**:
- Solo `text`, `voice`/`audio` y `photo` en chats privados pueden disparar procesamiento funcional.
- Media no soportada recibe aviso explícito.
- El webhook sigue devolviendo `200 {"status":"ok"}` para descartes seguros y `401/503` para errores de borde.

#### `app/services/private_media.py` o helper equivalente

**Responsabilidad**: Ejecutar el flujo común de media privada para audio e imágenes sin depender del proveedor de origen.

**Interfaz pública**:
```python
async def process_private_media(
    *,
    user_ctx: ResolvedUserContext,
    channel: str,
    recipient_id: str,
    msg_type: str,
    text_hint: str,
    media_bytes: bytes,
    media_mime_type: str | None,
    dispatcher: MessageDispatcher,
    agent: AgentLoop,
) -> None: ...
```

**Dependencias**: `transcription`, `receipt_ocr`, `AlertService`, `ExpenseService`, `MessageDispatcher`, `AgentLoop`.

**Invariantes**:
- El helper no conoce detalles de webhook específicos de Telegram o WhatsApp.
- Los mensajes de error/progreso se envían por el mismo canal del usuario.
- Un fallo en OCR o transcripción no deriva en una segunda respuesta conversacional engañosa.

#### `app/api/webhook.py`

**Responsabilidad**: Mantener el borde WhatsApp, pero delegando audio e imagen al helper compartido cuando aplique.

**Interfaz pública**:
```python
async def receive_message(request: Request, background_tasks: BackgroundTasks): ...
```

**Dependencias**: helper compartido de media, service de WhatsApp, paywall, settings.

**Invariantes**:
- La policy y los logs de seguridad de WhatsApp se preservan.
- El comportamiento observable de WhatsApp sigue estable después de la extracción.

### Data Model Changes

Sin cambios en modelo de datos. La identidad multi-canal ya existe desde la feature 017 y el procesamiento multimedia no requiere nuevas tablas ni migraciones.

### API Contract

### `POST /telegram/webhook`

**Request (audio privado)**:
```json
{
  "update_id": 123,
  "message": {
    "message_id": 10,
    "from": {"id": 777001},
    "chat": {"id": 777001, "type": "private"},
    "voice": {"file_id": "abc123", "mime_type": "audio/ogg", "file_size": 42000}
  }
}
```

**Request (imagen privada)**:
```json
{
  "update_id": 124,
  "message": {
    "message_id": 11,
    "from": {"id": 777001},
    "chat": {"id": 777001, "type": "private"},
    "photo": [
      {"file_id": "small"},
      {"file_id": "largest", "file_size": 1800000}
    ],
    "caption": "ticket super"
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
| 401 | `telegram_invalid_secret` | El secret del webhook no coincide. |
| 503 | `telegram_not_configured` | Telegram está deshabilitado o incompleto en config. |

### Testing Strategy

**Unit tests**:
- Cliente Telegram para `getFile`, normalización de metadata y descarga.
- Helper compartido de media para audio/image en casos felices y de error.
- Policy de Telegram media por MIME/tamaño.

**Integration tests**:
- `POST /telegram/webhook` para `voice`, `photo`, media rechazada y media fuera de alcance.
- Regresión de `POST /webhook` para audio e imagen en WhatsApp luego de extraer el helper.

**Mapping a scenarios funcionales**:
| Scenario | Test type | Qué valida |
|----------|-----------|------------|
| REQ-01 Scenario 01 | integration | Audio privado de Telegram se transcribe y entra al flujo del agente. |
| REQ-01 Scenario 02 | integration | Error de descarga/transcripción responde claramente y corta el flujo. |
| REQ-02 Scenario 01 | integration | Imagen privada dispara OCR y devuelve resultado equivalente al canal WhatsApp. |
| REQ-02 Scenario 02 | integration | OCR insuficiente informa al usuario sin romper memoria conversacional. |
| REQ-03 Scenario 01 | integration | Media fuera de policy se rechaza antes de descargar/procesar. |
| REQ-03 Scenario 02 | unit/integration | Metadata insuficiente corta temprano con mensaje de reintento. |
| REQ-04 Scenario 01 | integration | Documentos/video privados reciben aviso explícito. |
| REQ-04 Scenario 02 | integration | Grupos siguen descartados sin procesamiento multimedia. |
| REQ-05 Scenario 01 | unit/integration | Ambos canales reutilizan el helper y conservan respuestas equivalentes. |
| REQ-05 Scenario 02 | integration | WhatsApp mantiene sus paths multimedia sin regresión. |

### Implementation Risks

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Divergencia de mensajes de progreso/error entre canales | Med | Med | Centralizar textos base en el helper o documentarlos explícitamente en tests. |
| Bot API no provea `mime_type`/`file_size` en todos los casos | Med | High | Definir fallback controlado y rechazo temprano cuando no se pueda validar seguridad mínima. |
| La extracción del helper altere el paywall o el uso de `user_ctx` | Med | High | Mantener el gate de plan antes del procesamiento y cubrirlo con tests por canal. |
| Fotos de Telegram lleguen en múltiples tamaños | High | Med | Seleccionar explícitamente la variante más grande/útil antes de validar y descargar. |

### Notes for sdd-spec-writer

La spec técnica debe dejar claro que no se planea una abstracción multimedia genérica para todos los canales, sino una extracción mínima y pragmática del flujo privado ya existente. También conviene reflejar que el aviso de media fuera de alcance ya existe y debe preservarse como parte del comportamiento esperado.
