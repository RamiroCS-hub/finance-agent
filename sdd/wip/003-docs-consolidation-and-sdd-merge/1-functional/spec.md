# Functional Spec: Docs Consolidation and SDD Merge

**Feature**: `003-docs-consolidation-and-sdd-merge`
**Version**: 1.0
**Status**: Draft
**Date**: 2026-03-21

## Overview

Esta feature reorganiza la documentacion del proyecto para que el equipo tenga una unica fuente viva por tipo de conocimiento. `sdd/` debe quedar como lugar canonico para features y decisiones en curso, mientras que `docs/` y `README.md` concentran setup, operacion y referencia general.

El objetivo principal es reducir contradicciones entre `openspec/`, `sdd/`, `README.md` y documentos sueltos, manteniendo trazabilidad historica sin obligar al equipo a navegar varias taxonomias en paralelo.

## Actors

| Actor | Description |
|-------|-------------|
| Maintainer del repositorio | Ordena, escribe y mantiene la documentacion canonica. |
| Colaborador tecnico | Consulta setup, arquitectura y roadmap vivo para trabajar sobre el producto. |

## Requirements

### REQ-01: Fuente de verdad unica por categoria

La documentacion del proyecto MUST definir una ubicacion canonica para roadmap vivo, setup operativo e informacion historica.

#### Scenarios

**Scenario 01: Colaborador busca una feature activa**
```text
Given un colaborador que necesita el estado de una feature
When revisa el repositorio
Then encuentra el artefacto vivo dentro de sdd sin depender de openspec
```

**Scenario 02: Colaborador busca setup o deploy**
```text
Given un colaborador que necesita instalar o desplegar el producto
When abre la documentacion principal
Then encuentra la informacion en README o docs y no en artefactos de planning de features
```

### REQ-02: Migracion y archivo de contenido util

El proceso de consolidacion MUST preservar el contenido aprovechable de `openspec/` y SHALL marcar lo historico o deprecado de forma explicita.

#### Scenarios

**Scenario 01: Documento util en openspec**
```text
Given un documento de openspec con informacion todavia relevante
When se realiza la consolidacion
Then su contenido se migra o referencia desde la ubicacion canonica nueva
```

**Scenario 02: Documento historico**
```text
Given un documento que ya no representa el estado vivo del proyecto
When se ordena la documentacion
Then queda archivado o marcado como historico sin competir con la documentacion canonica
```

### REQ-03: Navegacion minima y onboarding claro

La documentacion SHOULD ofrecer una ruta de lectura minima para nuevos colaboradores.

#### Scenarios

**Scenario 01: Nuevo colaborador entra al repo**
```text
Given una persona nueva en el proyecto
When abre README.md
Then puede descubrir rapidamente donde esta setup, estado actual y features activas
```

**Scenario 02: Estructura final del repo**
```text
Given la documentacion ya consolidada
When un colaborador inspecciona las carpetas principales
Then la distribucion de docs resulta consistente y predecible
```

## Out of Scope

- Reescribir en profundidad cada documento historico si alcanza con archivarlo o resumirlo.
- Cambiar funcionalidad del producto mas alla de actualizar la documentacion asociada.
