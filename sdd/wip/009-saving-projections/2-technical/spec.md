# Technical Spec: Saving Projections

**Feature**: `009-saving-projections`
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-21
**Refs**: `1-functional/spec.md`

## Architecture Overview

La feature agrega un servicio de simulacion que consume historico de gastos y/o supuestos manuales para proyectar acumulacion de ahorro en el tiempo. El resultado puede cruzarse con metas vigentes cuando existan.

## Architecture Decision Records

### ADR-001: Simulacion deterministica en la primera version

- **Status**: Accepted
- **Context**: El valor de negocio no requiere un modelo predictivo complejo para la primera salida.
- **Decision**: Calcular proyecciones como escenarios deterministas basados en historico o inputs manuales.
- **Consequences**: Las respuestas son explicables y faciles de testear. A cambio, no capturan incertidumbre real.
- **Alternatives considered**: Modelos estadisticos o probabilisticos.

### ADR-002: Reusar metas como capa opcional

- **Status**: Accepted
- **Context**: Ya existe soporte parcial para metas de ahorro.
- **Decision**: Integrar la proyeccion con metas solo como enriquecimiento, no como dependencia obligatoria.
- **Consequences**: La feature es util aunque las metas no existan. A cambio, hay que mantener el acoplamiento bajo.
- **Alternatives considered**: Exigir una meta activa para simular.

## Component Design

### Projection service

**Responsabilidad**: construir escenarios de ahorro sobre historico o inputs manuales.

**Interfaz publica**:
```python
def project_savings(...) -> dict: ...
```

**Dependencias**: historial de gastos, reglas de frecuencia.

## Data Model

Sin cambios obligatorios en modelo de datos.

## API Contract

Sin cambios en API publica HTTP.

## Error Handling

- Si el usuario no provee suficientes supuestos y tampoco hay historico, la simulacion se rechaza con pedido de aclaracion.
- Los errores de proyeccion no deben bloquear otras consultas del agente.

## Testing Strategy

- **Unit tests**: acumulacion temporal y escenarios manuales.
- **Integration tests**: cruce con metas existentes.
- **E2E tests**: no requeridos en esta iteracion.

## Non-Functional Requirements

- **Performance**: calculos ligeros y sin dependencias externas.
- **Security**: usar solo datos del usuario autenticado.
- **Observability**: logs de simulacion y supuestos usados.
