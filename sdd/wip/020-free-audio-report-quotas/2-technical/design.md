## Design Document

**Feature**: 020-free-audio-report-quotas
**Diseñado por**: sdd-designer
**Fecha**: 2026-03-23

### Architecture Overview

La solución introduce una capa de cuotas persistentes sobre el paywall existente. El sistema conserva la validación binaria de plan por tipo de media, pero agrega un ledger de consumos por usuario y capacidad. Dos capacidades quedan metereadas solo para `FREE` en esta iteración:

- `audio_processing`: 5 usos por semana calendario local para FREE
- `expense_report_pdf`: 3 usos por mes calendario local para FREE

`PREMIUM` conserva acceso ilimitado y pasa por esta capa solo para obtener una decisión permisiva sin tope.

El flujo operativo se divide en precheck y consumo final:

```text
Incoming audio/report request
    -> resolve user + plan + timezone
    -> paywall static checks (allowed media / channel support)
    -> quota precheck (fast fail if FREE already exhausted)
    -> expensive work
         audio: download/transcribe/process
         report: build PDF/upload/send
    -> authoritative quota consume in DB
         insert usage event if still under limit
         skip duplicate audio if same source_ref already recorded
    -> user-facing success reply
```

El precheck evita trabajo caro cuando la cuota free ya está agotada. El consumo autoritativo ocurre al final y vuelve a verificar el conteo dentro de una transacción para no sobrepasar el límite por carreras concurrentes.

### ADRs

#### ADR-001: Persistir cuotas en PostgreSQL y no en memoria local

- **Context**: El usuario pide cuotas periódicas reales para el plan `FREE`; un contador en memoria se perdería con reinicios y no funcionaría bien con múltiples procesos.
- **Decision**: Persistir cada consumo en una tabla nueva de uso de plan y derivar la cuota vigente desde esa fuente de verdad.
- **Consequences**: Las cuotas sobreviven reinicios y escalan mejor. A cambio, la feature requiere migración Alembic y queries nuevas.
- **Alternatives considered**: Cache local del proceso. Se descarta porque rompería consistencia y recuperación tras restart.

#### ADR-002: Semana y mes se calculan por calendario local del usuario

- **Context**: “Semanal” y “mensual” son ambiguos si no se define timezone ni si la semana es rolling.
- **Decision**: Usar semana calendario y mes calendario según `default_timezone` del usuario, con fallback al mecanismo ya existente de inferencia/default.
- **Consequences**: La UX es predecible y alineada con el lenguaje de negocio. A cambio, hay que agregar helpers de ventana temporal y tests de borde.
- **Alternatives considered**: Rolling 7/30 días en UTC. Se descarta porque es menos intuitivo para el usuario y más opaco al comunicar resets.

#### ADR-003: Cobrar cuota solo en éxito, con precheck previo y consumo final autoritativo

- **Context**: No es aceptable descontar audio/reportes si falló la descarga, la transcripción o el envío del PDF.
- **Decision**: Hacer un precheck antes del trabajo pesado y un `consume_if_available(...)` al final dentro de transacción.
- **Consequences**: El usuario no pierde cupos por fallas transitorias. Puede haber algo de trabajo desperdiciado si dos requests compiten cerca del límite, pero el enforcement final sigue siendo correcto.
- **Alternatives considered**: Reservar el cupo antes de procesar y liberarlo si falla. Se descarta por complejidad y cleanup adicional.

#### ADR-004: Deduplicación pragmática solo donde haya identificador fuente estable

- **Context**: Los providers pueden reenviar el mismo audio; el tool de reportes no expone hoy un `message_id` canónico del turno.
- **Decision**: Guardar `source_ref` opcional y único para audio cuando el canal entregue un identificador estable del mensaje/media. No exigir deduplicación fuerte para reportes en esta iteración.
- **Consequences**: Se cubre el caso con mayor probabilidad de duplicado injusto sin agrandar demasiado el alcance brownfield.
- **Alternatives considered**: Diseñar una capa global de idempotency tokens para todo el agente. Se descarta por ser una refactorización mayor.

#### ADR-005: La cuota de reportes se enforcea en `ReportSkill`

- **Context**: El único camino actual que genera y envía reportes PDF está encapsulado en `ReportSkill._generate_expense_report`.
- **Decision**: Enforzar la cuota mensual ahí mismo, no en una capa genérica de tools.
- **Consequences**: El cambio queda localizado y con menos riesgo de efectos laterales. Si mañana aparece otro camino de reportes, deberá reutilizar el mismo servicio de cuotas.
- **Alternatives considered**: Meter la lógica en el runtime general del agente. Se descarta por acoplamiento innecesario.

### Component Design

#### `app/db/models.py`

**Responsabilidad**: declarar el modelo persistente de uso de cuotas.

**Nuevo modelo propuesto**:
```python
class PlanUsageEvent(Base):
    __tablename__ = "plan_usage_events"

    id: Mapped[int]
    user_id: Mapped[int]
    quota_key: Mapped[str]          # audio_processing | expense_report_pdf
    period_kind: Mapped[str]        # weekly | monthly
    source_ref: Mapped[str | None]
    consumed_at: Mapped[datetime]
    created_at: Mapped[datetime]
```

**Constraints**:
- índice por `(user_id, quota_key, consumed_at)`
- unique pragmático por `(user_id, quota_key, source_ref)` cuando `source_ref` no sea `NULL`

#### `app/services/plan_usage.py`

**Responsabilidad**: encapsular consultas de cuota, cálculo de ventanas y consumo autoritativo.

**Interfaz pública**:
```python
@dataclass
class QuotaDecision:
    allowed: bool
    limit: int
    used: int
    remaining: int
    quota_key: str
    period_kind: str

async def check_quota(
    session: AsyncSession,
    *,
    user_id: int,
    plan: str,
    quota_key: str,
    timezone: str,
    now: datetime | None = None,
) -> QuotaDecision: ...

async def consume_quota_if_available(
    session: AsyncSession,
    *,
    user_id: int,
    plan: str,
    quota_key: str,
    timezone: str,
    source_ref: str | None = None,
    now: datetime | None = None,
) -> QuotaDecision: ...
```

**Invariantes**:
- `FREE` usa esta capa para audio/reportes; `PREMIUM` retorna permitido sin límite.
- `consume_quota_if_available` es la fuente de verdad final del conteo.
- Si `source_ref` ya fue consumido previamente para ese usuario/capacidad, el método devuelve estado consistente sin duplicar el cargo.

#### `app/services/paywall.py`

**Responsabilidad**: seguir exponiendo límites estáticos por plan y declarar además las cuotas por capacidad.

**Interfaz pública adicional**:
```python
PLAN_LIMITS = {
    "FREE": {
        "quotas": {
            "audio_processing": {"limit": 5, "period": "weekly"},
            "expense_report_pdf": {"limit": 3, "period": "monthly"},
        }
    },
    "PREMIUM": {
        "quotas": {}
    }
}

def get_plan_quota(plan_type: str, quota_key: str) -> dict | None: ...
```

**Invariantes**:
- `check_media_allowed` conserva el gate por tipo de media.
- Las cuotas no reemplazan el gate estático; lo complementan.

#### `app/services/timezones.py`

**Responsabilidad**: calcular ventanas UTC para semana y mes locales.

**Interfaz pública adicional**:
```python
def utc_window_for_local_week(timezone_name: str, reference: datetime | None = None) -> tuple[datetime, datetime]: ...
def utc_window_for_local_month_by_timezone(timezone_name: str, reference: datetime | None = None) -> tuple[datetime, datetime]: ...
```

**Invariantes**:
- La semana empieza el lunes a las 00:00 locales.
- El fin de ventana es exclusivo.

#### `app/services/private_media.py`

**Responsabilidad**: procesar audio privado y disparar el consumo final solo si el audio terminó bien.

**Cambio de interfaz propuesto**:
```python
async def process_private_media(
    *,
    ...
    source_ref: str | None = None,
    on_audio_success: Callable[[str | None], Awaitable[None]] | None = None,
) -> None: ...
```

**Invariantes**:
- Si la transcripción falla, no se invoca `on_audio_success`.
- El callback de consumo se ejecuta solo después de obtener transcripción no vacía y antes de enviar la respuesta final del agente, o inmediatamente después según el wiring elegido.

#### `app/api/webhook.py` y `app/api/telegram_webhook.py`

**Responsabilidad**: resolver `user_id`/timezone, hacer precheck de audio y pasar `source_ref` del canal.

**Wiring esperado**:
- WhatsApp: `source_ref` desde `message["id"]` si el payload lo trae; fallback a `media_id`.
- Telegram: `source_ref` desde `message_id` o `update_id` según el dato más estable disponible.
- El precheck de `audio_processing` solo aplica si el usuario es `FREE`.

#### `app/agent/skills.py`

**Responsabilidad**: precheck y consumo final de `expense_report_pdf` dentro de `ReportSkill`.

**Invariantes**:
- Si el canal sigue siendo Telegram, el método retorna el mensaje actual de limitación de canal antes de tocar cuota.
- El precheck de reporte solo aplica si el usuario es `FREE`.
- La cuota se consume solo después de `send_document` exitoso.

### Data Model Changes

Se agrega una tabla nueva:

| Table | Purpose |
|-------|---------|
| `plan_usage_events` | Registrar cada consumo exitoso de cuota por usuario, capacidad y timestamp. |

La migración debe crear:
- FK a `users.id`
- índice por consulta temporal
- unique pragmático para `source_ref`

### API Contract

Sin cambios en endpoints públicos. Cambia el comportamiento observable:
- audio free puede ser rechazado por límite semanal agotado;
- reportes free pueden ser rechazados por límite mensual agotado;
- premium sigue sin ese tope.

### Testing Strategy

**Unit tests**:
- ventana semanal/mensual por timezone
- `PlanQuotaService.check_quota`
- `PlanQuotaService.consume_quota_if_available`
- deduplicación por `source_ref`

**Integration tests**:
- WhatsApp audio free bloqueado en el sexto audio semanal
- Telegram audio free bloqueado en el sexto audio semanal
- reporte free bloqueado en el cuarto PDF mensual
- reset de cuota al cambiar semana/mes local

**Mapping a scenarios funcionales**:
| Scenario | Test type | Qué valida |
|----------|-----------|------------|
| REQ-01 Scenario 01 | integration | Audio free dentro de cupo se procesa y consume 1 uso. |
| REQ-01 Scenario 02 | integration | Sexto audio semanal free se rechaza sin transcripción. |
| REQ-01 Scenario 03 | integration/unit | Falla de audio no consume cuota. |
| REQ-01 Scenario 04 | regression | PREMIUM no queda limitado por esta cuota semanal. |
| REQ-02 Scenario 01 | integration | Reporte PDF free exitoso consume 1 uso mensual. |
| REQ-02 Scenario 02 | integration | Cuarto reporte free del mes se rechaza. |
| REQ-02 Scenario 03 | integration/unit | Falla de PDF no consume cuota. |
| REQ-02 Scenario 04 | regression | PREMIUM no queda limitado por esta cuota mensual. |
| REQ-03 Scenario 01 | unit | Cambio de semana local resetea ventana. |
| REQ-03 Scenario 02 | unit | Cambio de mes local resetea ventana. |
| REQ-04 Scenario 01 | integration | Consumo persiste tras restart porque vive en DB. |
| REQ-04 Scenario 02 | unit/integration | Retry del mismo audio con igual `source_ref` no duplica consumo. |
| REQ-05 Scenario 01 | integration | Mensaje de límite semanal de audio es claro. |
| REQ-05 Scenario 02 | integration | Mensaje de límite mensual de reportes es claro. |
| REQ-06 Scenario 01 | regression | PREMIUM conserva acceso ilimitado a audio/reportes. |
| REQ-06 Scenario 02 | regression | Telegram sin reportes no consume cuota mensual. |

### Implementation Risks

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Carrera al consumir el último cupo free | Med | High | Recheck transaccional antes de insertar el evento final. |
| Mensajes de límite inconsistentes entre canales | Med | Med | Centralizar builders de mensaje en paywall o servicio de cuotas. |
| Timezone incorrecta para usuarios Telegram sin teléfono | Med | Med | Usar `default_timezone` ya persistida y fallback explícito del sistema. |
| El flujo de reportes quede parcialmente cobrado si falla `send_document` | Med | High | Consumir solo después de `send_document` exitoso. |

### Notes for sdd-spec-writer

La spec técnica debe dejar explícito que no se pretende un sistema general de billing, sino una capa mínima y persistente de cuotas de producto para `FREE`. También conviene remarcar que la semana es calendario local, no rolling, porque esa decisión afecta UX, tests y queries.
