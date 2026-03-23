# Implementation Progress

## Status

Completed on 2026-03-21.

## Implemented

- Added `WHATSAPP_APP_SECRET` and database URL normalization in [app/config.py](/Users/rcarnicer/Desktop/anotamelo/app/config.py).
- Added `build_engine()` to centralize DB engine creation in [app/db/database.py](/Users/rcarnicer/Desktop/anotamelo/app/db/database.py).
- Added configuration tests in [tests/test_config.py](/Users/rcarnicer/Desktop/anotamelo/tests/test_config.py).
- Documented Supabase deployment boundaries and checklist in [docs/deploy/supabase.md](/Users/rcarnicer/Desktop/anotamelo/docs/deploy/supabase.md).
- Updated `.env.example` and README to reflect deploy/runtime expectations.

## Notes

- The implementation keeps Supabase as the data platform and leaves the FastAPI webhook runtime external.
