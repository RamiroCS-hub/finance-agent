# Implementation Progress

## Status

Completed on 2026-03-21.

## Implemented

- Added [app/services/insights.py](/Users/rcarnicer/Desktop/anotamelo/app/services/insights.py) as the analytical layer over relational expense history, with period comparison and repetitive-spend leak detection.
- Updated [app/agent/tools.py](/Users/rcarnicer/Desktop/anotamelo/app/agent/tools.py) to expose `get_spending_comparison` and `get_spending_insights` as conversational tools.
- Updated [app/agent/core.py](/Users/rcarnicer/Desktop/anotamelo/app/agent/core.py) so the prompt routes comparison, leak-detection, and “dónde se me va la plata” intents through the new tools.
- Added focused coverage in [tests/test_insights.py](/Users/rcarnicer/Desktop/anotamelo/tests/test_insights.py) and extended [tests/test_tools.py](/Users/rcarnicer/Desktop/anotamelo/tests/test_tools.py) for tool wiring.
- Updated top-level docs to reflect that comparative and leak insights are now part of the current product state.

## Notes

- The original plan referenced `sheets.py`, but the implementation was intentionally moved to PostgreSQL-backed history because DB is now the operational source of truth.
- Heuristics are intentionally simple and explainable: period deltas plus repeated merchant/description patterns with meaningful accumulated impact.
