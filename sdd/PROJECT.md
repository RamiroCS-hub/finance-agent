# Project Configuration

## Stack
- **Lenguaje principal**: Python
- **Versión**: 3.11+
- **Framework**: FastAPI
- **Package manager**: pip

## Testing
- **Test runner**: pytest
- **Coverage mínimo**: 80%
- **Comando de tests**: `pytest -q`

## Linting
- **Linter**: no determinado
- **Comando**: no determinado

## Convenciones
- **Estilo de branch**: gitflow
- **Idioma de código**: inglés
- **Idioma de commits**: inglés

## Standards del proyecto
- Mantener `sdd/` como fuente de verdad para features activas y archivadas.
- No mezclar implementación con planificación: proposal/spec/design/tasks primero, código después de aprobación.
- Preservar compatibilidad con el flujo actual de WhatsApp, Google Sheets y PostgreSQL mientras se migra o refactoriza.

## Notas
- El producto actual es un bot de gastos por WhatsApp con FastAPI, Google Sheets como storage operativo y PostgreSQL para metadata relacional.
- La suite actual da una línea de base de 123 tests pasando y 1 fallando en `tests/test_agent_strip.py`.
