# Meta: Tools To Skills Separation

## Identificación
- **ID**: 013
- **Slug**: 013-tools-to-skills-separation
- **Tipo**: refactor
- **Estado**: done

## Resumen
Separar el gran `ToolRegistry` actual en skills o módulos de capacidades para reducir acoplamiento y permitir evolución por dominio.

## Stack detectado
- **Lenguaje**: Python
- **Framework**: FastAPI
- **Test runner**: pytest
- **Linter**: no determinado

## Git
- **Branch**: feature/tools-to-skills-separation
- **Base branch**: main

## Artefactos
- [x] 1-functional/spec.md
- [x] 2-technical/spec.md
- [x] 3-tasks/tasks.json
- [x] 4-implementation/progress.md
- [x] 5-verify/report.md

## Fechas
- **Creada**: 2026-03-21
- **Última actualización**: 2026-03-21
- **Completada**: 2026-03-21

## Notas
- Hoy `app/agent/tools.py` concentra demasiadas responsabilidades en una sola clase.
- El objetivo es separar herramientas por dominio sin cambiar el contrato observable del agente.
- La implementación quedó resuelta con un registry compositor y skills de dominio, manteniendo compatibilidad con los tests y con `ToolDefinition`.
