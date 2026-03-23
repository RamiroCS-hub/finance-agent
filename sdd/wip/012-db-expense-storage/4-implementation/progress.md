# Implementation Progress

## Status

Completed on 2026-03-21.

## Implemented

- Added relational `Expense` model and Alembic migration in [app/db/models.py](/Users/rcarnicer/Desktop/anotamelo/app/db/models.py) and [c1b3f0a2d9f1_add_expenses_table.py](/Users/rcarnicer/Desktop/anotamelo/migrations/versions/c1b3f0a2d9f1_add_expenses_table.py).
- Added DB-backed expense runtime service and Sheets import flow in [app/services/expenses.py](/Users/rcarnicer/Desktop/anotamelo/app/services/expenses.py).
- Rewired startup, agent core, and expense tools to use DB storage in [app/main.py](/Users/rcarnicer/Desktop/anotamelo/app/main.py), [app/agent/core.py](/Users/rcarnicer/Desktop/anotamelo/app/agent/core.py), and [app/agent/tools.py](/Users/rcarnicer/Desktop/anotamelo/app/agent/tools.py).
- Kept Sheets only for legacy import/export helpers in [app/services/sheets.py](/Users/rcarnicer/Desktop/anotamelo/app/services/sheets.py) and added the operational import script in [scripts/import_expenses_from_sheets.py](/Users/rcarnicer/Desktop/anotamelo/scripts/import_expenses_from_sheets.py).
- Updated env/docs and added unit coverage for DB expense storage and legacy import.

## Notes

- Runtime expense persistence no longer depends on Google Sheets credentials.
- Historical Sheets migration is explicit and admin-triggered; it is not part of normal webhook processing.
