# Technical Spec: Free Audio and Report Quotas

**Feature**: `020-free-audio-report-quotas`
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-23
**Refs**: `1-functional/spec.md`, `2-technical/design.md`

## Architecture Overview

La feature agrega cuotas persistentes por usuario sobre dos capacidades del plan `FREE`:

- `audio_processing`: límite `5`, período `weekly`
- `expense_report_pdf`: límite `3`, período `monthly`

La solución se monta sobre el dominio actual sin cambiar endpoints. El enforcement se apoya en:

1. resolución de `user_id`, plan y timezone;
2. precheck de cuota para cortar rápido cuando el cupo free ya está agotado;
3. procesamiento normal de audio o reporte;
4. consumo final autoritativo en base de datos solo si la operación salió bien.

```text
Channel/Skill -> plan gate -> quota precheck -> expensive work -> consume_if_available -> success reply
```

`PREMIUM` debe atravesar el mismo wiring sin tope efectivo para estas dos capacidades.

## Architecture Decision Records

### ADR-001: Source of truth de cuotas en DB

- **Status**: Accepted
- **Context**: Las cuotas deben persistir y no romperse al reiniciar o escalar procesos.
- **Decision**: Registrar eventos de consumo en PostgreSQL mediante una tabla nueva.
- **Consequences**: Se requiere migración y queries por ventana temporal; a cambio, el estado es durable.

### ADR-002: Calendario local del usuario

- **Status**: Accepted
- **Context**: El usuario pidió originalmente “semanal” para audios y “mensual” para reportes, y luego corrigió que eso aplica a FREE.
- **Decision**: Interpretar semana/mes en la timezone efectiva del usuario.
- **Consequences**: El contrato es entendible para el usuario, pero necesita helpers temporales y tests de borde.

### ADR-003: Consumo solo en éxito

- **Status**: Accepted
- **Context**: No es aceptable gastar cuota por errores transitorios.
- **Decision**: Consumir audio solo tras transcripción/procesamiento exitoso y reporte solo tras envío exitoso del PDF.
- **Consequences**: El usuario no pierde cupos por fallas, aunque puede existir trabajo desperdiciado cerca del límite.

## Component Design

### Modelo `PlanUsageEvent`

**Archivo**: `app/db/models.py`

```python
class PlanUsageEvent(Base):
    __tablename__ = "plan_usage_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    quota_key: Mapped[str] = mapped_column(String)
    period_kind: Mapped[str] = mapped_column(String)
    source_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    consumed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
```

**Expected constraints**:
- index compuesto sobre `user_id`, `quota_key`, `consumed_at`
- unique sobre `user_id`, `quota_key`, `source_ref` para deduplicar audio cuando `source_ref` exista

### Servicio `plan_usage`

**Archivo**: `app/services/plan_usage.py`

**Public API**:
```python
async def check_quota(..., quota_key: str, timezone: str) -> QuotaDecision: ...
async def consume_quota_if_available(..., quota_key: str, timezone: str, source_ref: str | None = None) -> QuotaDecision: ...
```

**Behavior**:
- si el plan no tiene cuota para `quota_key`, retorna permitido
- calcula la ventana UTC del período correspondiente
- cuenta eventos previos dentro de esa ventana
- en `consume_quota_if_available`, vuelve a contar dentro de transacción y recién ahí inserta
- si `source_ref` ya existe para el mismo usuario/capacidad, no duplica el consumo

### Extensión de `paywall`

**Archivo**: `app/services/paywall.py`

**Expected additions**:
```python
PLAN_LIMITS["FREE"]["quotas"] = {
    "audio_processing": {"limit": 5, "period": "weekly"},
    "expense_report_pdf": {"limit": 3, "period": "monthly"},
}
```

Se mantiene `check_media_allowed()` y se agrega un helper de metadata de cuota, por ejemplo:
```python
def get_plan_quota(plan_type: str, quota_key: str) -> dict | None: ...
```

### Helpers temporales

**Archivo**: `app/services/timezones.py`

**Expected additions**:
```python
def utc_window_for_local_week(timezone_name: str, reference: datetime | None = None) -> tuple[datetime, datetime]: ...
def utc_window_for_local_month_by_timezone(timezone_name: str, reference: datetime | None = None) -> tuple[datetime, datetime]: ...
```

### WhatsApp / Telegram audio wiring

**Archivos**:
- `app/api/webhook.py`
- `app/api/telegram_webhook.py`
- `app/services/private_media.py`

**Expected behavior**:
- resolver `user_id`, plan y timezone antes de transcribir
- hacer precheck de `audio_processing` solo si el usuario es `FREE`
- pasar `source_ref`
- consumir cuota solo si el audio realmente se procesó con éxito

### Report wiring

**Archivo**: `app/agent/skills.py`

**Expected behavior**:
- si `self.channel != "whatsapp"`, mantener el retorno actual y no tocar cuota
- si el canal soporta reporte, hacer precheck de `expense_report_pdf` solo si el usuario es `FREE`
- consumir cuota solo después de `send_document` exitoso

## Data Model

Nueva tabla:

| Table | Columns |
|-------|---------|
| `plan_usage_events` | `id`, `user_id`, `quota_key`, `period_kind`, `source_ref`, `consumed_at`, `created_at` |

Requiere nueva migración Alembic y `make migrate` durante implementación.

## API Contract

Sin endpoints nuevos ni payloads nuevos.

Cambios observables:
- Audio free puede devolver mensaje de “límite semanal alcanzado”.
- Reportes free pueden devolver mensaje de “límite mensual alcanzado”.
- Premium sigue ilimitado para audio/reportes.

## Error Handling

- Si la cuota está agotada, responder mensaje funcional claro y no exponer detalles de DB.
- Si el servicio de cuotas falla internamente, la implementación debe decidir fail-open o fail-closed de forma explícita en apply; la propuesta recomendada es fail-open con log de error para no cortar el producto por una falla auxiliar de contabilización.
- Si `consume_quota_if_available` detecta que otro request tomó el último cupo, responder el mensaje de límite aunque el trabajo pesado ya haya ocurrido.

## Testing Strategy

- **Unit tests**:
  - cálculo de ventanas por timezone
  - conteo de cuotas semanales y mensuales
  - dedupe de audio por `source_ref`
- **Integration tests**:
  - WhatsApp audio free: quinto permitido, sexto bloqueado
  - Telegram audio free: quinto permitido, sexto bloqueado
  - reportes free: tercero permitido, cuarto bloqueado
  - fallas de audio/reporte no consumen
- **Regression tests**:
  - PREMIUM sigue ilimitado para audio/reportes
  - Telegram sigue sin reportes PDF y no consume cuota al rechazar ese camino

## Non-Functional Requirements

- **Durability**: el consumo de cuotas debe persistir reinicios del backend.
- **Consistency**: el enforcement final debe impedir superar el límite aun con requests concurrentes razonables.
- **Observability**: logs deben permitir distinguir límite agotado, fallo técnico de provider y fallo interno del servicio de cuotas.

## Brownfield Annotations

<!-- extends: sdd/wip/018-telegram-audio-image-processing/2-technical/spec.md -->
<!-- extends: sdd/wip/017-telegram-channel-connection/2-technical/spec.md -->

Esta feature se apoya en la identidad multi-canal ya existente y en el helper compartido de media privada introducido para Telegram/WhatsApp. No reemplaza la política estática de media del plan; la complementa con cuotas de uso puntuales para `FREE` mientras preserva `PREMIUM` ilimitado.
