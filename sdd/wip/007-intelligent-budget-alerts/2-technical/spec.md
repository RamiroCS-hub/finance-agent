# Technical Spec: Intelligent Budget Alerts

**Feature**: `007-intelligent-budget-alerts`
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-21
**Refs**: `1-functional/spec.md`

## Architecture Overview

La feature agrega persistencia de reglas de presupuesto y un evaluador de alertas que corre al registrar un gasto o al consultar el estado financiero.

```text
register_expense -> budget evaluator -> optional alert payload
history query    -> anomaly evaluator -> optional alert payload
```

## Architecture Decision Records

### ADR-001: Presupuestos en storage relacional

- **Status**: Accepted
- **Context**: Los presupuestos son reglas de configuracion y no eventos de gasto.
- **Decision**: Persistir presupuestos y preferencias de alerta en PostgreSQL.
- **Consequences**: Facilita consultas y cambios futuros. A cambio, agrega tablas nuevas.
- **Alternatives considered**: Guardarlos en Sheets o en memoria.

### ADR-002: Anomalias por heuristicas explicables

- **Status**: Accepted
- **Context**: La primera version necesita señales utiles sin sobreingenieria.
- **Decision**: Usar comparaciones simples contra promedio o mediana recientes.
- **Consequences**: Las alertas son entendibles. A cambio, pueden aparecer falsos positivos moderados.
- **Alternatives considered**: Modelos estadisticos mas complejos.

## Component Design

### Budget service

**Responsabilidad**: crear, listar y resolver presupuestos activos por usuario.

**Interfaz publica**:
```python
async def save_budget(...) -> dict: ...
async def list_budgets(...) -> list[dict]: ...
```

**Dependencias**: DB relacional.

### Alert evaluator

**Responsabilidad**: evaluar desvio de presupuesto y anomalias por historial.

**Interfaz publica**:
```python
def evaluate_budget_alert(...) -> dict | None: ...
def evaluate_spike_alert(...) -> dict | None: ...
```

**Dependencias**: historial de gastos, presupuestos activos.

## Data Model

```python
class BudgetRule(Base):
    id: int
    user_id: int
    category: str
    period: str
    limit_amount: float
```

## API Contract

Sin cambios en API publica HTTP.

## Error Handling

- Sin historial suficiente no se emiten alertas anomalas.
- Si falta una regla de presupuesto, el evaluador solo retorna `None`.
- Los errores de calculo no deben bloquear el registro principal del gasto.

## Testing Strategy

- **Unit tests**: calculo de desvio y heuristicas de anomalia.
- **Integration tests**: persistencia y lectura de reglas de presupuesto.
- **E2E tests**: no requeridos en esta iteracion.

## Non-Functional Requirements

- **Performance**: la evaluacion debe ser ligera y no bloquear el flujo principal.
- **Security**: las reglas se consultan solo por el usuario autenticado.
- **Observability**: logs de alerta emitida y alerta descartada por falta de datos.
