# Technical Spec: Financial Education Coach

**Feature**: `011-financial-education-coach`
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-21
**Refs**: `1-functional/spec.md`

## Architecture Overview

La feature agrega una capa de reglas financieras y generacion de tips sobre el historial de gastos. Algunas respuestas son puramente deterministicas y otras dependen de una fuente externa opcional para inflacion.

## Architecture Decision Records

### ADR-001: Regla deterministica antes que generacion libre

- **Status**: Accepted
- **Context**: La feature necesita ser explicable y consistente.
- **Decision**: Calcular benchmarks y tips con reglas deterministicas sobre datos concretos antes de delegar estilo al LLM.
- **Consequences**: Las respuestas son trazables y testeables. A cambio, se reduce espontaneidad.
- **Alternatives considered**: Delegar toda la educacion al prompt del modelo.

### ADR-002: Inflacion como dependencia opcional y configurable

- **Status**: Accepted
- **Context**: No siempre habra una fuente de inflacion disponible o estable.
- **Decision**: Tratar el ajuste por inflacion como una capacidad opcional con fallback nominal.
- **Consequences**: La feature sigue siendo util sin bloquearse por una API externa. A cambio, algunas respuestas no tendran ajuste real.
- **Alternatives considered**: Requerir siempre una fuente externa.

## Component Design

### Education service

**Responsabilidad**: calcular benchmarks 50/30/20, fondo de emergencia y tips personalizados.

**Interfaz publica**:
```python
def evaluate_financial_health(...) -> dict: ...
def estimate_emergency_fund(...) -> dict: ...
def generate_personalized_tips(...) -> list[dict]: ...
```

**Dependencias**: historial de gastos, comparativas, configuracion opcional de inflacion.

## Data Model

Sin cambios obligatorios en modelo de datos para la primera version.

## API Contract

Sin cambios en API publica HTTP.

## Error Handling

- Si faltan datos historicos, devolver la limitacion explicitamente.
- Si falla la fuente de inflacion, degradar a analisis nominal.
- Los tips no deben generarse si no hay evidencia suficiente.

## Testing Strategy

- **Unit tests**: benchmark 50/30/20, fondo de emergencia y tips.
- **Integration tests**: flujo con y sin fuente de inflacion configurada.
- **E2E tests**: no requeridos en esta iteracion.

## Non-Functional Requirements

- **Performance**: calculos locales y livianos.
- **Security**: usar solo datos del usuario autenticado y no filtrar historico ajeno.
- **Observability**: logs de benchmark calculado, fallback nominal y tips emitidos.
