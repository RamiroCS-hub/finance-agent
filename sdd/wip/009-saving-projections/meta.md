# Meta: Saving Projections

## Identificación
- **ID**: 009
- **Slug**: 009-saving-projections
- **Tipo**: feature
- **Estado**: done

## Resumen
Agregar proyecciones de ahorro basadas en patrones históricos y escenarios de ajuste simples.

## Stack detectado
- **Lenguaje**: Python
- **Framework**: FastAPI
- **Test runner**: pytest
- **Linter**: no determinado

## Git
- **Branch**: feature/saving-projections
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
- La landing promete proyecciones concretas del tipo "si reducís X por semana, en Y meses ahorrás Z".
- Hoy no existe un motor de simulación sobre el histórico del usuario.
- La implementación se adaptó al storage relacional actual en vez de depender de `sheets.py`.
