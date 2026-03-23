# Proposal: DB Expense Storage

## Intent

Mover el almacenamiento operativo de gastos desde Google Sheets hacia la base de datos para que el bot dependa de una persistencia transaccional y desplegable en Supabase. Hoy el registro, las búsquedas, los resúmenes y el borrado del último gasto viven en un spreadsheet por usuario, lo que complica despliegue, testing, seguridad y evolución hacia features grupales.

## Scope

### In Scope
- Agregar un modelo relacional de gastos y su migración de base de datos.
- Refactorizar el flujo runtime del agente para registrar, consultar y borrar gastos desde DB en lugar de Google Sheets.
- Dejar un mecanismo de importación controlada para pasar histórico desde Sheets a DB y documentar la transición.

### Out of Scope
- Rediseñar en esta iteración el modelo de gastos compartidos o grupales de la feature `005`.
- Construir dashboards web, reporting avanzado o sincronización bidireccional permanente con Google Sheets.

## Approach

La migración debe introducir una capa de persistencia de gastos respaldada por PostgreSQL y conectar el agente a esa capa sin cambiar la experiencia conversacional. Google Sheets queda relegado a una utilidad de importación transitoria para histórico, mientras que el runtime diario deja de requerir credenciales ni acceso a la API de Google.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `app/db/models.py` | Modified | Nuevo modelo relacional de gastos y relaciones con usuario. |
| `migrations/versions/` | Modified | Nueva migración Alembic para crear la tabla de gastos. |
| `app/services/expenses.py` | New | Servicio/repository para alta, búsqueda, resumen y borrado desde DB. |
| `app/agent/core.py` | Modified | Reemplazo del wiring runtime dependiente de Sheets por un store de gastos en DB. |
| `app/agent/tools.py` | Modified | Tools de gastos consumen la nueva capa de persistencia. |
| `app/main.py` | Modified | Arranque sin dependencia obligatoria de Google Sheets. |
| `app/services/sheets.py` | Modified | Queda acotado a importación histórica o compatibilidad transitoria. |
| `tests/` | Modified | Cobertura de servicio DB, wiring del agente y regresiones funcionales. |
| `docs/` | Modified | Documentación de storage principal y transición desde Sheets. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Duplicar histórico al importar desde Sheets más de una vez | Med | Diseñar importación idempotente o con detección explícita de duplicados por usuario y payload importado. |
| Cambiar el orden del "último gasto" respecto al comportamiento actual | Med | Definir una regla estable de orden cronológico y cubrirla con tests de regresión. |
| Introducir diferencias en totales por parseo de fechas/monedas respecto a Sheets | Med | Conservar el mismo shape de datos de negocio y validar resúmenes con fixtures equivalentes. |
| Mantener dependencias residuales a Google en runtime | High | Separar el código de importación del código operativo y actualizar startup/docs/env. |

## Rollback Plan

El cambio se puede revertir restaurando el wiring del agente hacia `SheetsService` y manteniendo la tabla nueva sin uso mientras se corrige la migración. Si la importación histórica fallara, debe ser rerunnable o anulable por usuario sin afectar la operación diaria basada en DB.

## Dependencies

- Alembic y acceso a la base PostgreSQL/Supabase donde ya viven usuarios y configuraciones.
- Acceso al spreadsheet actual solo para importar histórico si se decide migrarlo.

## Success Criteria

- [ ] Los gastos nuevos se persisten en DB y pueden consultarse sin depender de Google Sheets.
- [ ] Resúmenes, búsqueda, recientes y borrado del último gasto operan sobre la DB y preservan el comportamiento observable actual.
- [ ] El bot puede arrancar y registrar gastos sin credenciales de Google configuradas.
- [ ] Existe un camino documentado para importar histórico desde Sheets a DB sin mezclar datos entre usuarios.
