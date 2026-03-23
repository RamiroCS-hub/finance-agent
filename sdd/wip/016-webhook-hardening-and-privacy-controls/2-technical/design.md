## Design Document

**Feature**: 016-webhook-hardening-and-privacy-controls
**Diseñado por**: sdd-designer
**Fecha**: 2026-03-23

### Architecture Overview

La solución endurece el pipeline actual sin rediseñarlo. El webhook deja de depender de la ausencia de configuración para decidir seguridad y pasa a un modelo explícito: request firmado por defecto, bypass local solo por flag consciente, preflight de media antes de descargar o enviar a servicios caros, y logging con minimización de datos desde el borde hasta el proveedor LLM.

La segunda línea del diseño es deny-by-default para cambios persistentes compartidos. Como el sistema actual no tiene una fuente confiable de roles administrativos de grupo, no debe aceptar que un mensaje grupal cambie comportamiento persistente de todo el chat. El path privado se mantiene y el path grupal se rechaza de forma controlada.

```text
Incoming webhook
   -> enforce signature policy
   -> parse payload / filters
   -> media preflight if needed
   -> enqueue background processing
      -> private scope: normal flows
      -> group scope: shared persistent config remains blocked

Operator logs
   -> redact phone/message content
   -> keep metadata, error code, request path
```

### ADRs

#### ADR-001: Fail-closed por defecto en autenticidad del webhook

- **Context**: El código actual acepta requests sin firma cuando el secreto está vacío, lo que degrada el control más importante del borde.
- **Decision**: Exigir firma válida por defecto y permitir bypass solo mediante una bandera explícita de desarrollo local.
- **Consequences**: Se elimina la degradación silenciosa; setups locales antiguos deberán configurarse de forma más explícita.
- **Alternatives considered**: Mantener el comportamiento actual y confiar en whitelist. Se descarta porque no protege contra requests forjados.

#### ADR-002: Deny-by-default para configuración persistente de grupos

- **Context**: El producto no dispone hoy de una autoridad confiable para decidir qué miembro puede cambiar reglas persistentes del grupo.
- **Decision**: Bloquear los cambios persistentes grupales hasta que exista una fuente verificable de autoridad; mantener permitidos los cambios privados.
- **Consequences**: Se elimina el vector de prompt injection persistente grupal, a costa de postergar una UX de administración grupal más rica.
- **Alternatives considered**: Inferir autoridad desde membership simple o permitir al primer escritor. Se descarta por falta de garantías y alto riesgo de abuso.

#### ADR-003: Minimización centralizada de datos en logs

- **Context**: El webhook y el provider LLM hoy registran texto de mensajes y cuerpos remotos que pueden contener datos sensibles.
- **Decision**: Introducir helpers de logging seguro y migrar los call sites sensibles a metadata reducida, códigos de error y contenido truncado/redactado.
- **Consequences**: Baja el riesgo de fuga por observabilidad; obliga a estandarizar qué se considera seguro loggear.
- **Alternatives considered**: Redactar caso por caso sin helper común. Se descarta porque es más fácil dejar huecos.

#### ADR-004: Preflight de media basado en metadata antes de descarga completa

- **Context**: OCR y transcripción son caros; hoy la app puede descargar media y recién después fallar.
- **Decision**: Consultar metadata mínima de la media, validar MIME/tamaño permitido y solo entonces descargar contenido binario.
- **Consequences**: Reduce costo y riesgo de abuso; agrega un paso adicional de validación previo a la descarga.
- **Alternatives considered**: Validar solo después de descargar. Se descarta por llegar tarde y consumir recursos innecesariamente.

### Component Design

#### `app/config.py`

**Responsabilidad**: Exponer política explícita de autenticidad y límites de media.

**Interfaz pública**:
```python
WHATSAPP_REQUIRE_SIGNATURE: bool
WHATSAPP_ALLOW_UNSIGNED_DEV_WEBHOOKS: bool
WHATSAPP_MAX_AUDIO_BYTES: int
WHATSAPP_MAX_IMAGE_BYTES: int
ALLOWED_AUDIO_MIME_TYPES: list[str]
ALLOWED_IMAGE_MIME_TYPES: list[str]
```

**Dependencias**: variables de entorno.

**Invariantes**:
- El modo seguro es el default.
- Un bypass local no se activa por ausencia de secreto sino por flag explícito.

#### `app/api/webhook.py`

**Responsabilidad**: Aplicar policy del borde, registrar de forma segura y cortar temprano los casos no permitidos.

**Interfaz pública**:
```python
def verify_webhook_signature(body: bytes, signature_header: str | None) -> None: ...
async def receive_message(request: Request, background_tasks: BackgroundTasks): ...
```

**Dependencias**: settings, helpers de logging seguro, servicio de media metadata, agente.

**Invariantes**:
- Un request inválido no procesa payload.
- El texto del usuario no se loggea en claro en paths nominales.
- Media inválida no llega a OCR ni transcripción.

#### `app/services/whatsapp.py`

**Responsabilidad**: Obtener metadata de media y descargar binarios solo cuando la policy lo permite.

**Interfaz pública**:
```python
async def get_media_metadata(media_id: str) -> dict | None: ...
async def download_media(media_id: str) -> bytes | None: ...
```

**Dependencias**: Meta Graph API, token de WhatsApp.

**Invariantes**:
- La URL de descarga se usa solo después de una validación de metadata exitosa.
- Los errores remotos no exponen cuerpos completos en logs.

#### `app/services/personality.py` + `app/agent/skills.py`

**Responsabilidad**: Permitir persistencia privada y negar persistencia grupal no verificable.

**Interfaz pública**:
```python
async def save_custom_prompt(
    session: AsyncSession,
    entity_id: str,
    prompt: str,
    is_group: bool = False,
) -> None: ...
```

**Dependencias**: session DB, `ChatConfiguration`, contexto del chat.

**Invariantes**:
- El scope privado sigue funcionando.
- El scope grupal no muta estado persistente cuando no hay autoridad verificable.

### Data Model Changes

Sin cambios en modelo de datos para esta iteración. El hardening se resuelve en policy de aplicación y no necesita migraciones.

### API Contract

#### `POST /webhook`

**Success**:
```json
{"status":"ok"}
```

**Errors**:
| Status | Code | Description |
|--------|------|-------------|
| 401 | invalid_signature | El request no presenta autenticidad válida bajo la policy activa |
| 413 | media_too_large | La media supera el máximo permitido |
| 415 | unsupported_media_type | La media no cumple la política de tipos soportados |

Nota: para mensajes válidos pero no procesables a nivel de producto, se mantiene el comportamiento actual de responder `200` a Meta una vez superada la capa de autenticidad.

### Testing Strategy

**Unit tests**:
- Policy de firma y bypass explícito.
- Helpers de redacción/logging seguro.
- Validación de media por tipo y tamaño.

**Integration tests**:
- `POST /webhook` firmado vs. no firmado.
- Rechazo temprano de media inválida.
- Persistencia privada permitida y persistencia grupal rechazada.

**Mapping a scenarios funcionales**:
| Scenario | Test type | Qué valida |
|----------|-----------|------------|
| REQ-01 Scenario 01 | integration | El webhook firmado sigue funcionando normalmente. |
| REQ-01 Scenario 02 | integration | El webhook sin autenticidad se rechaza fuera del bypass local explícito. |
| REQ-02 Scenario 01 | integration | El guardado privado sigue disponible. |
| REQ-02 Scenario 02 | integration | El guardado grupal no muta configuración persistente. |
| REQ-03 Scenario 01 | unit/integration | Los logs del webhook no incluyen texto crudo del usuario. |
| REQ-03 Scenario 02 | unit | Los errores del provider se registran sin cuerpo sensible. |
| REQ-04 Scenario 01 | integration | Media permitida continúa al pipeline correcto. |
| REQ-04 Scenario 02 | integration | Media inválida se corta antes del procesamiento pesado. |

### Implementation Risks

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Tests o entornos locales dependen del modo inseguro actual | High | Med | Introducir flag explícita y actualizar fixtures/docs en la misma entrega. |
| Metadata de media incompleta desde Meta | Med | Med | Manejar ausencia de datos con rechazo seguro o fallback documentado. |
| Redacción demasiado agresiva dificulta soporte | Med | Med | Conservar códigos, IDs parciales y contexto del módulo que falló. |
| Rechazo grupal genere confusión en usuarios | Med | Low | Devolver mensaje claro indicando que esa persistencia no está habilitada en grupos. |

### Notes for sdd-spec-writer

La spec técnica debe dejar explícito que esta iteración no implementa “admins de grupo”, sino un bloqueo seguro por falta de autoridad verificable. También conviene reflejar que la autenticidad del webhook pasa a ser una policy de configuración explícita y no una consecuencia accidental de que exista o no un secreto.
