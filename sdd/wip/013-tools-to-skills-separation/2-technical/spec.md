# Technical Spec: Tools To Skills Separation

**Feature**: `013-tools-to-skills-separation`
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-21
**Refs**: `1-functional/spec.md`

## Architecture Overview

La refactorización transforma `ToolRegistry` en un compositor liviano que instancia skills orientadas a dominio. Cada skill aporta un subconjunto de `ToolDefinition` y sus handlers concretos, apoyándose en un contexto común inyectado.

## Architecture Decision Records

### ADR-001: Mantener contrato de ToolDefinition

- **Status**: Accepted
- **Context**: `LLMProvider` ya consume `ToolDefinition` y no conviene cambiar ese contrato.
- **Decision**: Las skills siguen retornando `ToolDefinition`; el cambio está en la composición interna, no en el borde.
- **Consequences**: El refactor queda encapsulado y reduce riesgo sobre proveedores LLM.

### ADR-002: Context object compartido

- **Status**: Accepted
- **Context**: Varias tools dependen del mismo `phone`, `chat_type`, `group_id` y servicios.
- **Decision**: Introducir un contexto común de ejecución para skills en vez de pasar dependencias sueltas a cada handler.
- **Consequences**: Menos duplicación y mejor testabilidad. A cambio, aparece una nueva abstracción a sostener.

## Component Design

### Tool skill interface

**Responsabilidad**: exponer definiciones y handlers de un dominio.

**Interfaz pública**:
```python
class ToolSkill(Protocol):
    def definitions(self) -> list[ToolDefinition]: ...
```

### Tool registry composer

**Responsabilidad**: instanciar skills, unir definiciones y despachar ejecuciones.

### Shared tool context

**Responsabilidad**: encapsular teléfono, tipo de chat, grupo, stores y servicios compartidos.

## Data Model

Sin cambios de base de datos.

## API Contract

Sin cambios en API HTTP ni en el contrato de `ToolDefinition`.

## Error Handling

- Un fallo en una skill no debe romper el registry completo.
- Los errores de dispatch deben seguir devolviendo mensajes consistentes al agente.

## Testing Strategy

- **Unit tests**: skills individuales con mocks de contexto.
- **Integration tests**: composición del registry y compatibilidad del conjunto de tools.
- **Regression tests**: `tests/test_tools.py`, `tests/test_agent.py`, `tests/test_tools_cross_context.py`.

## Non-Functional Requirements

- **Maintainability**: agregar una nueva capacidad no debe requerir editar un archivo monolítico gigante.
- **Security**: cada skill debe respetar el scope autenticado ya existente.
- **Observability**: logs claros por skill durante ejecución y fallos.
