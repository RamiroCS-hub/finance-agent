# Technical Spec: Telegram Audio and Image Processing

**Feature**: 018-telegram-audio-image-processing
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-23
**Refs**: `1-functional/spec.md`, `2-technical/design.md`

## Architecture Overview

La solución extiende el webhook de Telegram para soportar tres entradas privadas: texto, audio e imagen. El borde de Telegram debe clasificar el tipo de update, resolver la identidad multi-canal ya existente, validar la media por tamaño/MIME y descargar bytes vía Bot API antes de invocar un flujo compartido de media privada. De esa manera, Telegram reutiliza la lógica ya probada para transcripción de audio y OCR de tickets, mientras WhatsApp se beneficia de una extracción mínima de lógica común.

Flujo propuesto:

```text
Telegram request
    ->
validate secret + dedup
    ->
classify private message
    -> text: AgentLoop.process(...)
    -> audio/image:
         getFile + normalize metadata
         -> validate Telegram media policy
         -> download bytes
         -> shared private media flow
              -> audio: transcribe -> AgentLoop.process(...)
              -> image: OCR -> register expense / confirmation / error
    -> unsupported: explicit notice
```

WhatsApp conserva su borde actual, pero delega audio e imágenes privadas al mismo flujo compartido para evitar drift funcional.

## Architecture Decision Records

### ADR-001: Compartir el pipeline privado de media entre canales

- **Status**: Accepted
- **Context**: La lógica de audio e imagen ya existe en WhatsApp y duplicarla en Telegram generaría drift inmediato.
- **Decision**: Extraer un helper/servicio compartido de media privada que reciba contexto canónico de usuario, tipo de media y adaptadores de salida.
- **Consequences**: Se reduce duplicación y se fuerza coherencia entre canales. La feature toca código brownfield y exige regresión de WhatsApp.
- **Alternatives considered**: Duplicar el flujo en el webhook de Telegram, descartado por costo de mantenimiento y riesgo funcional.

### ADR-002: Resolver archivos de Telegram en el service del canal

- **Status**: Accepted
- **Context**: Telegram Bot API usa `file_id` + `getFile` + descarga por `file_path`, distinto del patrón de Meta.
- **Decision**: Extender `app/services/telegram.py` con helpers de metadata y descarga, en vez de resolver HTTP inline en el webhook.
- **Consequences**: Mejor separación de responsabilidades y tests unitarios más claros del adaptador Telegram.
- **Alternatives considered**: Hacer llamadas HTTP desde `telegram_webhook.py`, descartado por mezclar transporte con orquestación.

### ADR-003: Policy propia de media para Telegram

- **Status**: Accepted
- **Context**: Los límites de WhatsApp ya existen, pero no deben arrastrarse implícitamente a otro proveedor.
- **Decision**: Agregar settings específicos de Telegram para tamaño máximo y MIME soportados de audio e imagen.
- **Consequences**: El tuning operativo queda desacoplado por canal y documentado de forma explícita.
- **Alternatives considered**: Reutilizar flags de WhatsApp, descartado por acoplamiento semántico entre proveedores.

### ADR-004: Fuera de alcance explícito, no silencioso

- **Status**: Accepted
- **Context**: El usuario pidió que el bot siempre avise cuando una capacidad todavía no existe.
- **Decision**: Mantener respuesta explícita para documentos, videos, stickers y demás media privada no soportada; grupos siguen fuera de alcance sin engañar al usuario.
- **Consequences**: La UX es honesta y el rollout puede ser incremental sin “falsos positivos” de soporte.
- **Alternatives considered**: Ignorar silenciosamente media fuera de alcance, descartado por mala experiencia y dificultad operativa.

## Component Design

### `app/services/telegram.py`

**Responsabilidad**: Encapsular Bot API para mensajes salientes y manejo de archivos de Telegram.

**Interfaz pública**:
```python
async def send_text(chat_id: str, message: str) -> str | None: ...
async def get_file(file_id: str) -> dict | None: ...
async def get_media_metadata(message: dict) -> dict | None: ...
async def download_file(file_path: str) -> bytes | None: ...
```

**Dependencias**: `httpx`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_API_BASE_URL`.

### `app/api/telegram_webhook.py`

**Responsabilidad**: Validar requests, clasificar texto/audio/imagen, avisar media fuera de alcance y delegar el procesamiento soportado.

**Interfaz pública**:
```python
@router.post("/telegram/webhook")
async def receive_telegram_update(request: Request, background_tasks: BackgroundTasks): ...
```

**Dependencias**: `ChannelIdentityService`, `MessageDispatcher`, `AgentLoop`, `app/services/telegram.py`, helper compartido de media.

### `app/services/private_media.py` o equivalente

**Responsabilidad**: Ejecutar el flujo de audio e imagen privada de forma agnóstica al canal.

**Interfaz pública**:
```python
async def process_private_media(
    *,
    user_ctx: ResolvedUserContext,
    channel: str,
    recipient_id: str,
    msg_type: str,
    media_bytes: bytes,
    media_mime_type: str | None,
    text_hint: str = "",
    reply_to_id: str | None = None,
) -> None: ...
```

**Dependencias**: `AgentLoop`, `MessageDispatcher`, `transcription`, `receipt_ocr`, `AlertService`, servicios de dominio.

### `app/api/webhook.py`

**Responsabilidad**: Seguir siendo el borde WhatsApp, pero usando el helper compartido para audio e imágenes privadas.

**Interfaz pública**:
```python
async def receive_message(request: Request, background_tasks: BackgroundTasks): ...
```

**Dependencias**: `whatsapp`, helper compartido de media, settings y gates de seguridad ya existentes.

## Data Model

Sin cambios en modelo de datos. La feature reutiliza `user_channels`, `ResolvedUserContext` y `users` existentes.

## API Contract

### `POST /telegram/webhook`

**Request (voice)**:
```json
{
  "update_id": 12345,
  "message": {
    "message_id": 10,
    "from": {"id": 777001, "first_name": "Ana"},
    "chat": {"id": 777001, "type": "private"},
    "voice": {"file_id": "voice-file-id", "mime_type": "audio/ogg", "file_size": 42000}
  }
}
```

**Request (photo)**:
```json
{
  "update_id": 12346,
  "message": {
    "message_id": 11,
    "from": {"id": 777001, "first_name": "Ana"},
    "chat": {"id": 777001, "type": "private"},
    "caption": "ticket supermercado",
    "photo": [
      {"file_id": "small"},
      {"file_id": "large", "file_size": 1800000}
    ]
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
| 401 | `telegram_invalid_secret` | Secret inválido o faltante |
| 503 | `telegram_not_configured` | Telegram sin configuración mínima |

Sin cambios en la API pública de WhatsApp.

## Error Handling

- Media fuera de policy o con metadata insuficiente corta temprano con un mensaje claro para el usuario.
- Documentos, videos y otros tipos fuera de alcance devuelven un aviso explícito y no se descargan.
- Fallos de `getFile` o de descarga se registran con contexto sanitizado y no disparan procesamiento adicional.
- Fallos de transcripción u OCR devuelven feedback directo al usuario y no continúan como si hubiera texto válido.
- El helper compartido debe evitar dobles respuestas al mismo update cuando el fallo ya fue comunicado.

## Testing Strategy

- **Unit tests**: cliente Telegram (`getFile`, normalización, descarga), validación de policy Telegram y helper compartido de media.
- **Integration tests**: webhook de Telegram para `voice`, `photo`, media fuera de policy y media fuera de alcance; regresión de audio/imagen en WhatsApp.
- **E2E tests**: no aplica en esta iteración; queda smoke manual en entorno real con webhook activo.

Mapeo a `1-functional/spec.md`:

- **REQ-01 Scenario 01**: test de audio privado feliz en Telegram.
- **REQ-01 Scenario 02**: test de error de descarga/transcripción.
- **REQ-02 Scenario 01**: test de imagen privada con OCR satisfactorio.
- **REQ-02 Scenario 02**: test de OCR insuficiente o ambiguo.
- **REQ-03 Scenario 01**: test de rechazo por MIME/tamaño.
- **REQ-03 Scenario 02**: test de metadata insuficiente.
- **REQ-04 Scenario 01**: test de aviso para documento/video.
- **REQ-04 Scenario 02**: test de descarte de grupo.
- **REQ-05 Scenario 01**: test de paridad del helper compartido entre canales.
- **REQ-05 Scenario 02**: test de no regresión de WhatsApp.

## Non-Functional Requirements

- **Performance**: el preflight de Telegram agrega como máximo un lookup `getFile` y una descarga por media soportada; no debe introducir round-trips redundantes.
- **Security**: ningún archivo de Telegram debe descargarse o procesarse sin validar secret del webhook y policy de tamaño/MIME del canal.
- **Observability**: logs con IDs parciales, tipo de media, resultado de policy y errores de proveedor, sin cuerpos completos ni datos sensibles.

## Brownfield Annotations

<!-- extends: sdd/wip/017-telegram-channel-connection/2-technical/spec.md#Architecture Overview -->
<!-- extends: sdd/wip/016-webhook-hardening-and-privacy-controls/2-technical/spec.md#Error Handling -->
<!-- extends: app/api/webhook.py#receive_message -->
