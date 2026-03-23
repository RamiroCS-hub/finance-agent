# Implementation Progress

## Status

Completed on 2026-03-21.

## Implemented

- Added OCR service and normalization/confidence gate in [app/services/receipt_ocr.py](/Users/rcarnicer/Desktop/anotamelo/app/services/receipt_ocr.py).
- Updated [app/api/webhook.py](/Users/rcarnicer/Desktop/anotamelo/app/api/webhook.py) to process image receipts instead of returning the old stub, including download, OCR, auto-register, and safe fallback/confirmation flows.
- Added `shop` as a persisted field for expenses and group expenses in [app/db/models.py](/Users/rcarnicer/Desktop/anotamelo/app/db/models.py), [2a964f1d1a45_add_shop_columns_to_expenses.py](/Users/rcarnicer/Desktop/anotamelo/migrations/versions/2a964f1d1a45_add_shop_columns_to_expenses.py), and the expense services.
- Updated [app/models/expense.py](/Users/rcarnicer/Desktop/anotamelo/app/models/expense.py) and [app/agent/tools.py](/Users/rcarnicer/Desktop/anotamelo/app/agent/tools.py) so text/OCR/group flows can carry the merchant name into storage.
- Updated env/docs and added OCR-focused test coverage.

## Notes

- OCR uses the configured Gemini key/model and only auto-registers when confidence is high enough.
- Medium-confidence tickets do not persist automatically; they ask the user to confirm by text.
