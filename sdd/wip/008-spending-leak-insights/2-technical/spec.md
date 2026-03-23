# Technical Spec: Spending Leak Insights

**Feature**: `008-spending-leak-insights`
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-21
**Refs**: `1-functional/spec.md`

## Architecture Overview

La feature agrega una capa analitica sobre el historial existente. El motor toma gastos historicos, agrupa por merchant, descripcion o categoria, y deriva comparativas y hallazgos.

## Architecture Decision Records

### ADR-001: Reusar historial existente como fuente primaria

- **Status**: Accepted
- **Context**: El valor de la feature depende de datos ya capturados por el producto.
- **Decision**: Construir los insights sobre consultas agregadas del storage actual antes de crear pipelines nuevos.
- **Consequences**: Se acelera la salida inicial. A cambio, la calidad depende de la consistencia del historico.
- **Alternatives considered**: ETL separado o warehouse analitico.

### ADR-002: Heuristicas simples para merchants y recurrencia

- **Status**: Accepted
- **Context**: La deteccion perfecta es costosa y fragil al principio.
- **Decision**: Empezar con agrupaciones por descripcion normalizada, categoria y frecuencia.
- **Consequences**: El sistema es explicable y mantenible. A cambio, puede perder algunos casos complejos.
- **Alternatives considered**: Clasificacion inteligente completa por merchant.

## Component Design

### Insights service

**Responsabilidad**: ejecutar comparativas y detectar patrones repetitivos.

**Interfaz publica**:
```python
def compare_spending_periods(...) -> dict: ...
def detect_spending_leaks(...) -> list[dict]: ...
```

**Dependencias**: historial de gastos, reglas de normalizacion.

## Data Model

Sin cambios obligatorios en modelo de datos.

## API Contract

Sin cambios en API publica HTTP.

## Error Handling

- Si no hay datos suficientes, el servicio devuelve un estado vacio explicito.
- Un fallo analitico no debe romper resumenes o registros existentes.

## Testing Strategy

- **Unit tests**: comparativas y deteccion de patrones.
- **Integration tests**: consultas sobre historicos simulados realistas.
- **E2E tests**: no requeridos en esta iteracion.

## Non-Functional Requirements

- **Performance**: las consultas deben mantenerse razonables sobre historicos medianos.
- **Security**: los insights solo se calculan con datos del usuario autenticado.
- **Observability**: logs de insight generado y causas de descarte por datos insuficientes.
