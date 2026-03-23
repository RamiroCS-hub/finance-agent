## Design Document

**Feature**: 020-local-cache-rate-limit
**Diseñado por**: sdd-designer
**Fecha**: 2026-03-23

### Architecture Overview

La solución mantiene el punto de enforcement del rate limit en `POST /webhook`, pero reemplaza la capa de almacenamiento del `RateLimitService`. En lugar de delegar en Redis, el servicio mantiene dos mapas en memoria del proceso: uno para contadores por `(phone, window_bucket)` y otro para cooldowns de notificación por `phone`. Cada acceso limpia entradas vencidas antes de evaluar el nuevo mensaje.

Con esto desaparece la dependencia operativa de Redis en startup y el wiring del rate limit se vuelve puramente local. El trade-off aceptado es que el enforcement pasa a ser por instancia y el estado se pierde cuando el proceso reinicia.

```text
verify signature
    ->
parse payload + filters
    ->
rate_limiter.allow_message(phone)
    -> local counter window
    -> local notify cooldown
    -> allowed/block
```

### ADRs

#### ADR-001: Usar cache local por proceso en lugar de Redis

- **Context**: El rate limit actual introduce Redis como dependencia operativa, lo que complica el deploy en entornos simples como el target inicial en Render.
- **Decision**: Reemplazar el backend Redis por almacenamiento en memoria local dentro del `RateLimitService`.
- **Consequences**: El deploy se simplifica y el wiring baja de complejidad; el límite deja de ser compartido entre instancias y se resetea al reiniciar el proceso.
- **Alternatives considered**: Mantener Redis o mover el estado a Postgres. Se descartan en esta iteración por costo operativo o complejidad innecesaria.

#### ADR-002: Mantener el enforcement en el webhook antes del trabajo pesado

- **Context**: El motivo principal del rate limit sigue siendo evitar OCR, transcripción y llamadas al LLM cuando ya se superó el cupo.
- **Decision**: No mover el control de lugar; solo cambia el backend del servicio.
- **Consequences**: Se preserva el contrato existente del webhook y se minimiza la superficie del cambio.
- **Alternatives considered**: Aplicarlo más tarde dentro del agente. Se descarta por llegar tarde al ahorro de costo.

#### ADR-003: Limpieza oportunista de entradas vencidas

- **Context**: Un cache local sin limpieza puede crecer indefinidamente con números viejos.
- **Decision**: Limpiar claves expiradas de forma oportunista en cada evaluación del servicio y limitar la estructura a datos efímeros por ventana/cooldown.
- **Consequences**: Se evita sumar un scheduler o tarea aparte. A cambio, la complejidad se concentra dentro del servicio y debe quedar bien testeada.
- **Alternatives considered**: Limpieza en background. Se descarta por complejidad adicional para un estado tan pequeño.

### Component Design

#### `app/services/rate_limit.py`

**Responsabilidad**: Evaluar cupo por número usando estructuras locales efímeras y administrar cooldown de notificación.

**Interfaz pública**:
```python
from dataclasses import dataclass

@dataclass(slots=True)
class RateLimitDecision:
    allowed: bool
    remaining: int
    retry_after_seconds: int
    should_notify: bool

class RateLimitService:
    async def allow_message(self, phone: str) -> RateLimitDecision: ...
```

**Dependencias**: parámetros de configuración y función de tiempo.

**Invariantes**:
- El estado se indexa por teléfono y bucket temporal.
- Las entradas vencidas no deben seguir afectando decisiones nuevas.
- El servicio no depende de red ni de clientes externos.

#### `app/main.py`

**Responsabilidad**: Crear el `RateLimitService` local y pasarlo al webhook sin inicializar Redis.

**Interfaz pública**:
```python
@app.on_event("startup")
async def startup(): ...
```

**Dependencias**: `settings`, `RateLimitService`, webhook init.

**Invariantes**:
- El arranque del backend para rate limiting no requiere `REDIS_URL`.
- El wiring del agente y del webhook sigue intacto fuera de este cambio.

#### `tests/test_rate_limit.py`

**Responsabilidad**: Validar allow/block, expiración, reinicio de ventana y cooldown con el backend local.

**Interfaz pública**:
```python
@pytest.mark.asyncio
async def test_rate_limit_allows_until_threshold_then_blocks(): ...
```

**Dependencias**: `RateLimitService`, control determinista del reloj.

### Data Model Changes

Sin cambios en modelo de datos.

### API Contract

Sin cambios en API pública. `POST /webhook` conserva `{"status":"ok"}` para eventos válidos aunque el mensaje quede limitado.

### Testing Strategy

**Unit tests**:
- Ventana fija, bloqueo, reintento y cooldown del `RateLimitService`.
- Limpieza de entradas expiradas para evitar estado residual.

**Integration tests**:
- Webhook con mensajes permitidos y excedidos usando el nuevo wiring local.
- Arranque de la app con rate limit habilitado y sin `REDIS_URL`.

**Mapping a scenarios funcionales**:
| Scenario | Test type | Qué valida |
|----------|-----------|------------|
| REQ-01 Scenario 01 | integration | Mensaje dentro del cupo sigue al pipeline normal. |
| REQ-01 Scenario 02 | integration | Mensaje excedido no dispara procesamiento pesado. |
| REQ-02 Scenario 01 | integration | La app arranca sin Redis y el webhook sigue operativo. |
| REQ-02 Scenario 02 | doc/review | La documentación aclara el alcance por instancia. |
| REQ-03 Scenario 01 | unit | Una nueva ventana resetea el cupo. |
| REQ-03 Scenario 02 | unit/integration | El cooldown evita advertencias repetidas. |

### Implementation Risks

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Condiciones de carrera si múltiples requests modifican el estado local al mismo tiempo | Med | Med | Mantener la estructura simple y evaluar si hace falta protección mínima en la implementación. |
| Falsa sensación de límite global en despliegues con múltiples réplicas | High | Med | Documentar explícitamente el carácter por instancia y evitar prometer enforcement distribuido. |
| Fugas de memoria por falta de cleanup | Med | Med | Cubrir cleanup con tests y limpiar oportunistamente en cada acceso. |

### Notes for sdd-spec-writer

La spec técnica debe remarcar que este cambio es un trade-off consciente de simplicidad operativa. No hay que venderlo como equivalente distribuido a Redis; hay que documentarlo como rate limiting local best-effort.
