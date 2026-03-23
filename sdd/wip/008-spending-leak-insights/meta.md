# Meta: Spending Leak Insights

## Identificación
- **ID**: 008
- **Slug**: 008-spending-leak-insights
- **Tipo**: feature
- **Estado**: done

## Resumen
Agregar insights de detección de fugas de gasto, comparativas temporales y oportunidades concretas de ahorro.

## Stack detectado
- **Lenguaje**: Python
- **Framework**: FastAPI
- **Test runner**: pytest
- **Linter**: no determinado

## Git
- **Branch**: feature/spending-leak-insights
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
- Esta feature agrupa claims cercanos de la landing: detectar dónde se pierde plata, comparativas semanales/mensuales y lectura de gastos repetitivos de bajo valor.
- No hay hoy analítica histórica más allá de totales y breakdown por categoría.
- La implementación se adaptó al runtime actual en PostgreSQL en vez de `sheets.py`, porque el storage operativo ya fue migrado a DB.
