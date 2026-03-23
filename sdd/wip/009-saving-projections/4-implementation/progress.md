# Implementation Progress

## Status

Completed on 2026-03-21.

## Implemented

- Added [app/services/projections.py](/Users/rcarnicer/Desktop/anotamelo/app/services/projections.py) with deterministic saving projections for both manual scenarios and historical category-based scenarios.
- Updated [app/agent/tools.py](/Users/rcarnicer/Desktop/anotamelo/app/agent/tools.py) to expose `project_savings` as a conversational tool.
- Updated [app/agent/core.py](/Users/rcarnicer/Desktop/anotamelo/app/agent/core.py) so the prompt routes future-looking saving questions through the projection tool.
- Added focused coverage in [tests/test_projections.py](/Users/rcarnicer/Desktop/anotamelo/tests/test_projections.py) and expanded [tests/test_tools.py](/Users/rcarnicer/Desktop/anotamelo/tests/test_tools.py).
- Updated product docs/current-state to reflect that saving projections are now part of the live feature set.

## Notes

- The implementation uses the current PostgreSQL expense history instead of the older `sheets.py` references in the original plan.
- Weekly projections intentionally use a simple 4-weeks-per-month approximation to keep the output deterministic and explainable.
