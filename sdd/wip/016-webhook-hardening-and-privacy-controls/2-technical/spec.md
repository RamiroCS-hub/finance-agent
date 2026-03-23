# Technical Spec: Webhook Hardening and Privacy Controls

**Feature**: 016-webhook-hardening-and-privacy-controls
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-23
**Refs**: `1-functional/spec.md`, `2-technical/design.md`

## Architecture Overview

La solución endurece el pipeline de ingreso y observabilidad existente sin cambiar el modelo funcional del bot. El primer cambio es una policy explícita de autenticidad en el webhook: request firmado obligatorio por defecto, con un bypass local opt-in solo para desarrollo. El segundo cambio es deny-by-default para mutaciones persistentes de alcance grupal mientras no exista una autoridad verificable. El tercero es una capa de minimización de datos en logs, y el cuarto un preflight de media basado en metadata para cortar archivos fuera de política antes de OCR o transcripción.

Flujo propuesto:

```text
verify signature policy
    ->
parse payload + supported message filter
    ->
media metadata preflight (if audio/image)
    -> invalid: stop early, reply safely
    -> valid: enqueue background processing
        -> private persistent config allowed
        -> group persistent config denied by default

logs
    -> safe metadata only
    -> no raw user text / no remote response bodies
```

## Architecture Decision Records

### ADR-001: Exigir autenticidad del webhook por default

- **Status**: Accepted
- **Context**: El código actual depende de que `WHATSAPP_APP_SECRET` exista para recién allí exigir firma, lo que degrada la seguridad si la configuración está incompleta.
- **Decision**: Introducir una policy explícita en config que requiera firma por defecto y permita bypass solo con una bandera local consciente.
- **Consequences**: Se evita el modo inseguro implícito; ambientes locales y tests deben declarar con claridad cuándo quieren bypass.
- **Alternatives considered**: Mantener el secreto como “switch” implícito de seguridad. Se descarta por ambigüedad y riesgo operativo.

### ADR-002: Negar mutaciones persistentes grupales sin autoridad verificable

- **Status**: Accepted
- **Context**: `save_personality` puede escribir configuración compartida para un grupo sin una fuente confiable de autoridad.
- **Decision**: Mantener permitido el scope privado y rechazar el scope grupal mientras el producto no pueda verificar autoridad suficiente.
- **Consequences**: Se elimina el vector de prompt injection persistente en grupos; la feature de personalidad grupal queda explícitamente pospuesta.
- **Alternatives considered**: Reutilizar `GroupMember.role` actual. Se descarta porque hoy no hay una fuente confiable ni sincronizada para poblarlo.

### ADR-003: Centralizar logging seguro

- **Status**: Accepted
- **Context**: Hay varios call sites que registran texto de usuario, teléfonos completos o cuerpos remotos.
- **Decision**: Usar helpers compartidos o utilidades locales estandarizadas para redacción/truncado y migrar los puntos críticos a metadata mínima.
- **Consequences**: Menos riesgo de fuga por logs; obliga a una convención consistente de observabilidad.
- **Alternatives considered**: Corregir solo los casos más obvios. Se descarta por dejar superficies abiertas.

### ADR-004: Preflight de media basado en metadata

- **Status**: Accepted
- **Context**: El webhook puede activar OCR/transcripción sobre media que no debería procesarse o cuyo tamaño ya excede la policy.
- **Decision**: Consultar metadata en Graph API, validar tamaño/MIME por tipo de mensaje y descargar binarios solo cuando la media sea elegible.
- **Consequences**: Reduce costo y abuso; agrega una dependencia de metadata en el path multimedia.
- **Alternatives considered**: Validar solo por `mime_type` del payload o validar tras la descarga. Se descartan por insuficiente cobertura o costo tardío.

## Component Design

### `app/config.py`

**Responsabilidad**: Exponer flags explícitas de autenticidad y límites de media.

**Interfaz pública**:
```python
WHATSAPP_REQUIRE_SIGNATURE: bool
WHATSAPP_ALLOW_UNSIGNED_DEV_WEBHOOKS: bool
WHATSAPP_MAX_AUDIO_BYTES: int
WHATSAPP_MAX_IMAGE_BYTES: int
WHATSAPP_ALLOWED_AUDIO_MIME_TYPES: list[str]
WHATSAPP_ALLOWED_IMAGE_MIME_TYPES: list[str]
```

**Dependencias**: variables de entorno.

### `app/api/webhook.py`

**Responsabilidad**: Aplicar policy de seguridad de borde y decidir rechazos tempranos.

**Interfaz pública**:
```python
def verify_webhook_signature(body: bytes, signature_header: str | None) -> None: ...
async def receive_message(request: Request, background_tasks: BackgroundTasks): ...
```

**Dependencias**: settings, `whatsapp.get_media_metadata`, agente, helpers de logging seguro.

### `app/services/whatsapp.py`

**Responsabilidad**: Separar metadata de descarga y encapsular logging seguro de Graph API.

**Interfaz pública**:
```python
async def get_media_metadata(media_id: str) -> dict | None: ...
async def download_media(media_id: str) -> bytes | None: ...
```

**Dependencias**: Meta Graph API, token de WhatsApp.

### `app/services/personality.py`

**Responsabilidad**: Persistir prompts privados y rechazar persistencia grupal no verificable.

**Interfaz pública**:
```python
async def save_custom_prompt(
    session: AsyncSession,
    entity_id: str,
    prompt: str,
    is_group: bool = False,
) -> None: ...
```

**Dependencias**: `User`, `Group`, `ChatConfiguration`, contexto del chat.

### `app/services/llm_provider.py`

**Responsabilidad**: Reportar fallos del proveedor sin exponer cuerpos remotos sensibles.

**Interfaz pública**:
```python
def _log_http_error(self, operation: str, exc) -> None: ...
```

**Dependencias**: logger del módulo, helper de sanitización.

## Data Model

Sin cambios en modelo de datos. La restricción grupal se resuelve por policy y no por migración.

## API Contract

### `POST /webhook`

**Response 200**:
```json
{
  "status": "ok"
}
```

**Errors**:
| Status | Code | Description |
|--------|------|-------------|
| 401 | invalid_signature | El request no cumple la policy de autenticidad |
| 413 | media_too_large | La media excede el límite configurado |
| 415 | unsupported_media_type | La media no cumple la policy de MIME soportado |

No se agregan endpoints nuevos. La API pública del producto sigue siendo el mismo webhook.

## Error Handling

- Si la policy exige firma y el request no la cumple, el webhook falla antes de leer el payload como confiable.
- Si el bypass local explícito está activo, el webhook puede aceptar requests sin firma solo en ese modo.
- Si la metadata de media no puede obtenerse o no cumple policy, el flujo multimedia se corta antes de OCR/transcripción y el usuario recibe una respuesta segura.
- Si un usuario intenta persistir configuración grupal, el sistema rechaza la operación sin mutar `ChatConfiguration`.
- Los errores del proveedor LLM se loggean con código, operación y contexto mínimo, pero sin cuerpo remoto completo.

## Testing Strategy

- **Unit tests**: policy de firma, helpers de logging seguro, evaluación de metadata/tamaño.
- **Integration tests**: webhook firmado/no firmado, media aceptada/rechazada y guardado privado vs grupal.
- **E2E tests**: no aplica en esta iteración.

Referencia a scenarios de `1-functional/spec.md`:

- **REQ-01 Scenario 01**: test de webhook firmado aceptado.
- **REQ-01 Scenario 02**: test de webhook no firmado rechazado sin bypass.
- **REQ-02 Scenario 01**: test de persistencia privada exitosa.
- **REQ-02 Scenario 02**: test de persistencia grupal rechazada sin cambios.
- **REQ-03 Scenario 01**: test de logging del webhook sin texto crudo.
- **REQ-03 Scenario 02**: test de provider error logging sin body sensible.
- **REQ-04 Scenario 01**: test de media dentro de policy que sigue al pipeline.
- **REQ-04 Scenario 02**: test de media fuera de policy que se corta temprano.

## Non-Functional Requirements

- **Performance**: el preflight agrega como máximo una consulta ligera de metadata antes de descargar media; no debe introducir procesamiento pesado extra.
- **Security**: el sistema no debe confiar en `message.from` antes de validar autenticidad y no debe aceptar persistencia grupal sin autoridad verificable.
- **Observability**: los logs deben conservar IDs parciales, módulo y código de error suficientes para soporte sin incluir contenido sensible del usuario o de proveedores.

## Brownfield Annotations

<!-- extends: sdd/wip/004-phone-scope-security-hardening/2-technical/spec.md#Architecture Overview -->
<!-- extends: app/api/webhook.py#receive_message -->
