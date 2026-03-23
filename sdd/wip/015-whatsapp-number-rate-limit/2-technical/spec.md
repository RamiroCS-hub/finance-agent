# Technical Spec: WhatsApp Number Rate Limit

**Feature**: 015-whatsapp-number-rate-limit
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-23
**Refs**: `1-functional/spec.md`, `2-technical/design.md`

## Architecture Overview

La solución agrega un `RateLimitService` respaldado por Redis y lo integra en `POST /webhook` antes de disparar procesamiento asíncrono. El webhook sigue su pipeline actual de autenticidad, parseo y filtros básicos; recién cuando ya sabe que el mensaje sería procesable consulta el cupo por `phone`.

Flujo:

```text
verify_webhook_signature
    ->
parse payload + resolve phone/message type
    ->
supported/whitelist/group mention filters
    ->
rate_limiter.allow_message(phone)
    -> allowed: background_tasks.add_task(...)
    -> blocked: optional cooldown notice + return {"status":"ok"}
```

## Architecture Decision Records

### ADR-001: Redis como backend compartido del cupo por teléfono

- **Status**: Accepted
- **Context**: El proyecto ya incluye Redis en dependencias e infraestructura local.
- **Decision**: Guardar el estado del rate limit en Redis usando keys por número de WhatsApp.
- **Consequences**: El límite queda consistente entre instancias; la app necesita config y wiring de Redis.
- **Alternatives considered**: Memoria local del proceso, descartada por inconsistencia entre réplicas.

### ADR-002: Enforce temprano en el webhook

- **Status**: Accepted
- **Context**: El trabajo costoso ocurre después de `background_tasks.add_task(...)`.
- **Decision**: Cortar por rate limit antes de OCR, transcripción y `AgentLoop`.
- **Consequences**: Reduce costo y carga; obliga a que el webhook conozca el rate limiter.
- **Alternatives considered**: Aplicarlo dentro del agente o servicios downstream, descartado por llegar tarde.

### ADR-003: Fail-open si Redis falla

- **Status**: Accepted
- **Context**: Redis es una dependencia operativa, no el corazón del negocio.
- **Decision**: Ante error del rate limiter, procesar el mensaje igual y loggear el incidente.
- **Consequences**: La protección se debilita temporalmente, pero la disponibilidad del bot se mantiene.
- **Alternatives considered**: Fail-closed, descartado por riesgo de indisponibilidad total.

### ADR-004: Cooldown de advertencia separado

- **Status**: Accepted
- **Context**: Un aviso de “esperá un momento” mejora UX, pero repetirlo a cada mensaje es ruido.
- **Decision**: Manejar una key efímera adicional por número para decidir si corresponde notificar o no.
- **Consequences**: Se evita spam de advertencias con un costo mínimo de estado extra.
- **Alternatives considered**: Nunca avisar o avisar siempre, descartados por UX pobre.

## Component Design

### `app/services/rate_limit.py`

**Responsabilidad**: Evaluar cupo por número, devolver decisión y administrar cooldown de aviso.

**Interfaz pública**:
```python
from dataclasses import dataclass

@dataclass
class RateLimitDecision:
    allowed: bool
    remaining: int
    retry_after_seconds: int
    should_notify: bool

class RateLimitService:
    async def allow_message(self, phone: str) -> RateLimitDecision: ...
```

**Dependencias**: cliente Redis async y parámetros de configuración.

### `app/config.py`

**Responsabilidad**: Exponer configuración del rate limiter.

**Interfaz pública**:
```python
REDIS_URL: str
WHATSAPP_RATE_LIMIT_ENABLED: bool
WHATSAPP_RATE_LIMIT_MAX_MESSAGES: int
WHATSAPP_RATE_LIMIT_WINDOW_SECONDS: int
WHATSAPP_RATE_LIMIT_NOTIFY_COOLDOWN_SECONDS: int
```

**Dependencias**: variables de entorno.

### `app/main.py`

**Responsabilidad**: Crear el cliente Redis y el `RateLimitService`, e inyectarlo en el webhook.

**Interfaz pública**:
```python
@app.on_event("startup")
async def startup(): ...
```

**Dependencias**: settings, Redis client, webhook init.

### `app/api/webhook.py`

**Responsabilidad**: Aplicar el límite operativo por número antes de encolar trabajo.

**Interfaz pública**:
```python
def init_dependencies(agent, rate_limiter=None) -> None: ...
@router.post("/webhook")
async def receive_message(request: Request, background_tasks: BackgroundTasks): ...
```

**Dependencias**: `RateLimitService`, `whatsapp.send_text`, `BackgroundTasks`.

## Data Model

Sin cambios en modelo de datos ni migraciones.

## API Contract

Sin cambios en endpoints ni payloads públicos. Para eventos válidos, el webhook mantiene:

```json
{"status":"ok"}
```

Aunque el mensaje quede bloqueado por rate limit.

## Error Handling

- Si `WHATSAPP_RATE_LIMIT_ENABLED` es `false`, el webhook omite el control.
- Si Redis falla o no está disponible, el webhook procesa el mensaje igual y emite log con contexto del teléfono.
- Si el número supera el cupo, el webhook no llama a `_process_message_background`.
- Si `should_notify` es `true`, el webhook agenda un único aviso corto por cooldown; si es `false`, bloquea en silencio hacia el usuario pero no hacia Meta.

## Testing Strategy

- **Unit tests**: `tests/test_rate_limit.py` cubre allow, block, expiración y cooldown.
- **Integration tests**: `tests/test_webhook.py` cubre allow, block y fail-open en el endpoint real.
- **E2E tests**: no aplica en esta iteración.

Mapeo a scenarios de `1-functional/spec.md`:

- **REQ-01 Scenario 01**: verificar que un mensaje dentro del cupo llame al agente o al path esperado.
- **REQ-01 Scenario 02**: verificar que un mensaje excedido no dispare procesamiento en background.
- **REQ-02 Scenario 01**: comprobar que la clave se basa en `message.from` independientemente del contexto.
- **REQ-02 Scenario 02**: asegurar que mensajes descartados por tipo o sin mención no tocan el rate limiter.
- **REQ-03 Scenario 01**: simular error de Redis y confirmar fail-open.
- **REQ-03 Scenario 02**: verificar que `should_notify` no se repita dentro del cooldown.

## Non-Functional Requirements

- **Performance**: una sola evaluación Redis por mensaje soportado; no introducir múltiples round-trips innecesarios.
- **Security**: el límite se apoya sobre el número remitente solo después de validar firma del webhook.
- **Observability**: agregar logs estructurados para decisiones bloqueadas, retries sugeridos y fallos del backend de rate limit.

## Brownfield Annotations

<!-- extends: app/api/webhook.py#receive_message -->
<!-- extends: sdd/wip/004-phone-scope-security-hardening/2-technical/spec.md#Architecture Overview -->
