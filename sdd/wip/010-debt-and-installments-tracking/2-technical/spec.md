# Technical Spec: Debt and Installments Tracking

**Feature**: `010-debt-and-installments-tracking`
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-21
**Refs**: `1-functional/spec.md`

## Architecture Overview

La feature introduce un dominio nuevo para obligaciones futuras que vive en persistencia relacional y se consulta desde el agente.

## Architecture Decision Records

### ADR-001: Las obligaciones futuras se modelan fuera del ledger de gastos corrientes

- **Status**: Accepted
- **Context**: Mezclar cuotas pendientes con gastos ya ejecutados distorsiona resumenes y reglas de negocio.
- **Decision**: Crear entidades separadas para cuotas/deudas y agregarlas a respuestas financieras cuando corresponda.
- **Consequences**: Mayor claridad de dominio. A cambio, aumenta el numero de consultas y modelos.
- **Alternatives considered**: Persistirlas como gastos normales con tags.

### ADR-002: La primera version soporta cuotas fijas y deudas simples

- **Status**: Accepted
- **Context**: Hay muchas variantes posibles de deuda.
- **Decision**: Limitar el alcance inicial a cuotas fijas y saldos simples.
- **Consequences**: La salida es implementable rapido. A cambio, no cubre casos financieros complejos.
- **Alternatives considered**: Modelado completo desde el inicio.

## Component Design

### Liabilities service

**Responsabilidad**: registrar, listar y cerrar cuotas o deudas.

**Interfaz publica**:
```python
async def create_liability(...) -> dict: ...
async def get_monthly_commitment(...) -> dict: ...
async def close_liability(...) -> dict: ...
```

**Dependencias**: DB relacional, tool registry.

## Data Model

```python
class Liability(Base):
    id: int
    user_id: int
    kind: str
    description: str
    monthly_amount: float
    remaining_periods: int
    status: str
```

## API Contract

Sin cambios en API publica HTTP.

## Error Handling

- No registrar obligaciones con datos criticos faltantes.
- No incluir obligaciones cerradas en el compromiso mensual.
- Rechazar operaciones sobre IDs inexistentes con mensajes accionables.

## Testing Strategy

- **Unit tests**: calculo de compromiso mensual y cierre de obligaciones.
- **Integration tests**: persistencia y consulta por usuario.
- **E2E tests**: no requeridos en esta iteracion.

## Non-Functional Requirements

- **Performance**: consultas ligeras por usuario.
- **Security**: ninguna obligacion puede verse fuera del usuario autenticado.
- **Observability**: logs de alta, cierre y consulta de obligaciones.
