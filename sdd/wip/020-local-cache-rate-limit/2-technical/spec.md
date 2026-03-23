# Technical Spec: Local Cache Rate Limit

**Feature**: `020-local-cache-rate-limit`
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-23
**Refs**: `1-functional/spec.md`, `2-technical/design.md`

## Architecture Overview

La solución conserva el `RateLimitService` y su integración temprana en `POST /webhook`, pero reemplaza el backend Redis por un cache local en memoria. El servicio calcula el bucket temporal actual, actualiza un contador por `(phone, bucket)` y consulta un cooldown de notificación por `phone`, todo dentro del proceso de FastAPI.

```text
verify_webhook_signature
    ->
parse payload + resolve phone/message type
    ->
supported/whitelist/group mention filters
    ->
rate_limiter.allow_message(phone)
    -> local counter map
    -> local notify cooldown map
    -> allowed: background_tasks.add_task(...)
    -> blocked: optional cooldown notice + return {"status":"ok"}
```

## Architecture Decision Records

### ADR-001: Cache local como backend del rate limit

- **Status**: Accepted
- **Context**: Redis complica el deploy para un uso que hoy puede tolerar consistencia por instancia.
- **Decision**: Guardar el estado del rate limit en estructuras locales en memoria dentro del proceso.
- **Consequences**: El despliegue se simplifica y desaparece la dependencia externa. A cambio, el límite no es global entre réplicas y se pierde al reiniciar.
- **Alternatives considered**: Redis y Postgres. Se descartan en esta iteración por complejidad operativa.

### ADR-002: Enforce temprano en el webhook

- **Status**: Accepted
- **Context**: La protección sigue teniendo sentido solo si ocurre antes de OCR, transcripción y `AgentLoop`.
- **Decision**: Mantener el check en `app/api/webhook.py` antes de encolar trabajo pesado.
- **Consequences**: El ahorro de costo y CPU se preserva y el cambio queda acotado.
- **Alternatives considered**: Aplicarlo más tarde en el pipeline, descartado por ineficiente.

### ADR-003: Cleanup oportunista del estado efímero

- **Status**: Accepted
- **Context**: Las estructuras locales deben expirar entradas viejas para no crecer sin control.
- **Decision**: Limpiar claves vencidas al momento de evaluar nuevos mensajes, sin agregar workers internos.
- **Consequences**: Implementación más simple y suficiente para volumen esperado. A cambio, el servicio necesita lógica interna un poco más cuidadosa.
- **Alternatives considered**: Scheduler en background, descartado por sobreingeniería.

## Component Design

### `app/services/rate_limit.py`

**Responsabilidad**: evaluar allow/block por teléfono usando estado local efímero.

**Interfaz pública**:
```python
@dataclass(slots=True)
class RateLimitDecision:
    allowed: bool
    remaining: int
    retry_after_seconds: int
    should_notify: bool

class RateLimitService:
    async def allow_message(self, phone: str) -> RateLimitDecision: ...
```

**Dependencias**: configuración de cupo/ventana/cooldown y función de tiempo.

### `app/main.py`

**Responsabilidad**: crear el rate limiter local e inyectarlo en el webhook.

**Interfaz pública**:
```python
@app.on_event("startup")
async def startup(): ...
```

**Dependencias**: `settings`, `RateLimitService`.

### `app/config.py`

**Responsabilidad**: exponer solo la configuración necesaria del rate limiter local.

**Interfaz pública**:
```python
WHATSAPP_RATE_LIMIT_ENABLED: bool
WHATSAPP_RATE_LIMIT_MAX_MESSAGES: int
WHATSAPP_RATE_LIMIT_WINDOW_SECONDS: int
WHATSAPP_RATE_LIMIT_NOTIFY_COOLDOWN_SECONDS: int
```

**Dependencias**: variables de entorno.

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
- Si el rate limiter local encuentra estado vencido, lo limpia antes de decidir.
- Si el número supera el cupo, el webhook no llama a `_process_message_background`.
- Si `should_notify` es `true`, el webhook agenda un único aviso corto por cooldown.

## Testing Strategy

- **Unit tests**: `tests/test_rate_limit.py` cubre allow, block, expiración, cleanup y cooldown.
- **Integration tests**: `tests/test_webhook.py` cubre allow, block y arranque sin Redis.
- **E2E tests**: no aplica en esta iteración.

Mapeo a scenarios de `1-functional/spec.md`:

- **REQ-01 Scenario 01**: verificar que un mensaje dentro del cupo llame al agente o al path esperado.
- **REQ-01 Scenario 02**: verificar que un mensaje excedido no dispare procesamiento en background.
- **REQ-02 Scenario 01**: confirmar que la app arranca y limita sin depender de `REDIS_URL`.
- **REQ-02 Scenario 02**: dejar explícito en docs/tests que el límite no se comparte entre instancias.
- **REQ-03 Scenario 01**: simular avance del reloj y confirmar reset de ventana.
- **REQ-03 Scenario 02**: verificar que `should_notify` no se repita dentro del cooldown.

## Non-Functional Requirements

- **Performance**: la decisión debe resolverse localmente sin round-trips de red.
- **Security**: el límite sigue evaluándose solo después de validar la firma del webhook.
- **Observability**: agregar logs para bloqueos y, cuando aplique, para cleanup o decisiones de cooldown relevantes.

## Brownfield Annotations

<!-- extends: sdd/wip/015-whatsapp-number-rate-limit/2-technical/spec.md -->

Esta feature reemplaza el backend Redis de la feature 015, pero mantiene la ubicación del enforcement y el contrato observable del webhook.
