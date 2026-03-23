# Technical Spec: Docs Consolidation and SDD Merge

**Feature**: `003-docs-consolidation-and-sdd-merge`
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-21
**Refs**: `1-functional/spec.md`

## Architecture Overview

La solucion define una jerarquia documental simple:

```text
README.md -> puerta de entrada
docs/     -> setup, operacion, deploy, referencias
sdd/      -> roadmap vivo, specs, tasks y estado de features
openspec/ -> historico o migrado
```

No hay cambios de runtime. El trabajo consiste en clasificar, mover, resumir y enlazar contenido de forma controlada.

## Architecture Decision Records

### ADR-001: `sdd/` es la unica fuente viva para features

- **Status**: Accepted
- **Context**: Hoy `openspec/` y `sdd/` describen cambios y decisiones en paralelo.
- **Decision**: Dejar `sdd/` como unica fuente viva para features activas, specs y tasks.
- **Consequences**: Se simplifica el proceso de trabajo. A cambio, hay que migrar o archivar material previo.
- **Alternatives considered**: Mantener ambas taxonomias con reglas de convivencia. Se descarta por complejidad.

### ADR-002: `docs/` concentra documentacion operativa y de referencia

- **Status**: Accepted
- **Context**: El README no debe crecer indefinidamente y los artefactos SDD no son el lugar para setup operativo.
- **Decision**: Mover setup, deploy y runbooks a `docs/`, dejando README como indice principal.
- **Consequences**: La navegacion mejora y la documentacion operativa queda separada del roadmap.
- **Alternatives considered**: Colapsar todo en README. Se descarta por escala.

### ADR-003: `openspec/` se conserva solo como historico transitorio

- **Status**: Accepted
- **Context**: Puede haber informacion util que no conviene perder.
- **Decision**: Migrar lo vigente y dejar el resto marcado como historico o pendiente de archivo.
- **Consequences**: Se mantiene trazabilidad. A cambio, existira una fase de transicion.
- **Alternatives considered**: Borrar `openspec/` de una vez.

## Component Design

### Documentation index

**Responsabilidad**: exponer una entrada clara hacia setup, operacion y roadmap vivo.

**Interfaz publica**:
```text
README.md
```

**Dependencias**: estructura final de `docs/` y `sdd/`.

### Docs taxonomy

**Responsabilidad**: agrupar documentos tecnicos por tema operativo.

**Interfaz publica**:
```text
docs/
```

**Dependencias**: contenido migrado desde README, docs previas y openspec.

### SDD workspace

**Responsabilidad**: contener project config, features activas y archivadas.

**Interfaz publica**:
```text
sdd/PROJECT.md
sdd/wip/
sdd/features/
```

**Dependencias**: proceso SDD del equipo.

## Data Model

Sin cambios en modelo de datos.

## API Contract

Sin cambios en API publica.

## Error Handling

- Los movimientos de archivos deben preservar trazabilidad.
- Si una pieza de contenido no puede clasificarse con certeza, debe quedar marcada como historica o pendiente en vez de mezclarse con la canonica.

## Testing Strategy

- **Unit tests**: no aplica.
- **Integration tests**: chequeo manual de enlaces, rutas y consistencia del arbol.
- **E2E tests**: smoke manual de onboarding documental.

Cada scenario funcional se valida por inspeccion del arbol final y recorrido de lectura.

## Non-Functional Requirements

- **Performance**: no aplica.
- **Security**: evitar incluir secretos o ejemplos con credenciales reales al reordenar docs.
- **Observability**: registrar en el changelog o progress log que contenido se migro y que se archivo.

## Brownfield Annotations

<!-- deprecates: openspec/changes -->
<!-- extends: sdd/PROJECT.md -->
