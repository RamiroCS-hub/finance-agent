## Design Document

**Feature**: 015-whatsapp-number-rate-limit
**Diseñado por**: sdd-designer
**Fecha**: 2026-03-23

### Architecture Overview

El rate limiter se integra en el webhook HTTP antes de `background_tasks.add_task(...)`, una vez que el request ya pasó validación de firma, parseo del payload, filtro de tipo soportado y chequeos básicos como whitelist o mención grupal. La clave operativa es el `message.from`, porque es la identidad remitente que ya gobierna el scope funcional del producto.

La implementación recomendada usa Redis porque ya está en dependencias y en la infraestructura local. Cada request soportado consulta un servicio `RateLimitService` que decide `allow` o `block` para ese teléfono dentro de una ventana configurable. Si el mensaje queda bloqueado, el webhook responde igual `200 OK` a Meta y puede programar un aviso corto con cooldown para no repetirlo en cada intento.

```text
Meta webhook
   -> verify signature
   -> parse payload / supported message filter
   -> resolve sender phone
   -> RateLimitService.allow(phone)
      -> allow: enqueue background processing
      -> block: skip heavy work, maybe enqueue cooldown notice
```

### ADRs

#### ADR-001: Usar Redis compartido como backend del rate limiter

- **Context**: El proyecto ya incluye Redis en `docker-compose.yml` y `redis` en `requirements.txt`, pero no lo está usando aún.
- **Decision**: Persistir el estado del rate limit en Redis para que el cupo por teléfono sea consistente entre instancias del webhook.
- **Consequences**: La política se vuelve shared-state y apta para escalar horizontalmente, a costa de agregar wiring/configuración de Redis a la app.
- **Alternatives considered**: Memoria local del proceso. Se descarta como default porque no comparte estado entre réplicas y puede ser inconsistente.

#### ADR-002: Aplicar el control antes del trabajo pesado, no dentro del agente

- **Context**: OCR, transcripción y llamadas al LLM son costosamente evitables si el mensaje ya está excedido.
- **Decision**: Hacer el check en `app/api/webhook.py` antes de encolar `_process_message_background`.
- **Consequences**: Se protege CPU, red y costo aguas abajo; el webhook necesita una dependencia nueva además del agente.
- **Alternatives considered**: Rate limiting dentro de `_process_message_background` o `AgentLoop`. Se descarta porque llega demasiado tarde.

#### ADR-003: Fail-open ante error del backend de rate limit

- **Context**: Un fallo de Redis no debe tumbar el bot entero.
- **Decision**: Si el rate limiter no puede evaluar el cupo, el webhook procesa el mensaje igual y deja trazabilidad en logs.
- **Consequences**: Se prioriza disponibilidad sobre enforcement estricto cuando hay incidente de infraestructura.
- **Alternatives considered**: Fail-closed. Se descarta porque convertiría una caída de Redis en caída total del bot.

#### ADR-004: Aviso de límite con cooldown separado

- **Context**: Avisar al usuario mejora UX, pero repetir la advertencia en cada mensaje limita mal y ensucia el canal.
- **Decision**: Guardar un cooldown de notificación por número para enviar como máximo un aviso por ventana definida.
- **Consequences**: Mejor feedback con bajo ruido; suma una segunda key efímera por número.
- **Alternatives considered**: Silenciar siempre o avisar siempre. Se descartan por UX pobre o spam.

### Component Design

#### `app/services/rate_limit.py`

**Responsabilidad**: Resolver decisiones allow/block por número y manejar cooldown de notificación.

**Interfaz pública**:
```python
class RateLimitDecision(TypedDict):
    allowed: bool
    remaining: int
    retry_after_seconds: int
    should_notify: bool

class RateLimitService:
    async def allow_message(self, phone: str) -> RateLimitDecision: ...
```

**Dependencias**: cliente Redis async, configuración de ventana/cupo/cooldown.

**Invariantes**:
- La key principal siempre está namespaced por teléfono.
- Cada mensaje soportado consume a lo sumo una unidad.
- `should_notify` solo es `True` una vez por cooldown.

#### `app/api/webhook.py`

**Responsabilidad**: Decidir si el mensaje sigue al pipeline o se corta por rate limit.

**Interfaz pública**:
```python
def init_dependencies(agent, rate_limiter=None) -> None: ...
@router.post("/webhook")
async def receive_message(request: Request, background_tasks: BackgroundTasks): ...
```

**Dependencias**: agente, `RateLimitService`, `whatsapp.send_text`.

**Invariantes**:
- El webhook mantiene `200 OK` para Meta en requests válidos.
- Los mensajes descartados por tipo/mención no consumen cupo.
- Los mensajes rate-limited no llegan a `_process_message_background`.

### Data Model Changes

Sin cambios en PostgreSQL ni migraciones.

### API Contract

Sin cambios de API pública. `POST /webhook` conserva respuesta `200 {"status":"ok"}` para eventos válidos, incluso cuando un mensaje se bloquea por rate limit.

### Testing Strategy

**Unit tests**:
- Validar el conteo, expiración de ventana y cooldown de notificación del `RateLimitService`.

**Integration tests**:
- Verificar desde `tests/test_webhook.py` que mensajes por debajo del límite sí se encolan y por encima no.
- Verificar que errores de Redis hagan fail-open.

**Mapping a scenarios funcionales**:
| Scenario | Test type | Qué valida |
|----------|-----------|------------|
| REQ-01 Scenario 01 | integration | El webhook encola el mensaje cuando el número está dentro del cupo. |
| REQ-01 Scenario 02 | integration | El webhook no llama al agente ni a background cuando el número excede el cupo. |
| REQ-02 Scenario 01 | unit/integration | La misma clave por teléfono cubre privado y grupo. |
| REQ-02 Scenario 02 | integration | Eventos descartados antes del pipeline no consumen rate limit. |
| REQ-03 Scenario 01 | integration | Un error de Redis deja pasar el mensaje y registra fallo. |
| REQ-03 Scenario 02 | unit/integration | La advertencia no se repite en cada intento durante cooldown. |

### Implementation Risks

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Error de off-by-one en ventana fija | Med | Med | Cubrir límites exactos con tests unitarios. |
| Reuso incorrecto de cliente Redis en startup | Low | Med | Centralizar wiring en `main.py` y mantener una sola instancia. |
| Latencia extra en webhook | Low | Med | Hacer una sola operación Redis por request y mantener mensajes bloqueados fuera del pipeline pesado. |

### Notes for sdd-spec-writer

La spec técnica debe dejar explícito que el contrato HTTP a Meta no cambia y que el backend de rate limit falla abierto. También conviene fijar defaults prudentes en config para no bloquear usuarios reales apenas se habilite.
