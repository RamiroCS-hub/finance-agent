# Meta: DB Expense Storage

## Identificación
- **ID**: 012
- **Slug**: 012-db-expense-storage
- **Tipo**: feature
- **Estado**: done

## Resumen
Migrar la persistencia operativa de gastos desde Google Sheets hacia la base de datos sin romper el flujo actual de WhatsApp.

## Stack detectado
- **Lenguaje**: Python
- **Framework**: FastAPI
- **Test runner**: pytest
- **Linter**: no determinado

## Git
- **Branch**: feature/db-expense-storage
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
- Hoy los gastos se registran, buscan, resumen y eliminan exclusivamente via `app/services/sheets.py`.
- La base PostgreSQL ya existe para usuarios, metas y configuraciones, pero no tiene una tabla de gastos.
- El cambio debe remover la dependencia runtime de credenciales de Google para operar el bot y dejar un camino controlado para importar histórico.
