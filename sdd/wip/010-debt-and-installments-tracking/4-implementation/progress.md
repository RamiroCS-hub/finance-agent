# Implementation Progress

## Status

Completed on 2026-03-21.

## Implemented

- Added `Liability` persistence in [app/db/models.py](/Users/rcarnicer/Desktop/anotamelo/app/db/models.py) and [94d5d1a6d0a4_add_liabilities_table.py](/Users/rcarnicer/Desktop/anotamelo/migrations/versions/94d5d1a6d0a4_add_liabilities_table.py).
- Added [app/services/liabilities.py](/Users/rcarnicer/Desktop/anotamelo/app/services/liabilities.py) for creating, querying, and closing active obligations.
- Exposed liabilities in the agent through `create_liability`, `get_monthly_commitment`, and `close_liability`.
- Added coverage in [tests/test_liabilities.py](/Users/rcarnicer/Desktop/anotamelo/tests/test_liabilities.py), plus registry/model updates.

## Notes

- Obligations remain outside the executed-expense ledger to avoid polluting current spend summaries.
- The first version intentionally models only fixed installments and simple debts.
