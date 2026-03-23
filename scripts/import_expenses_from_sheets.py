from __future__ import annotations

import argparse
import asyncio
import json

from app.services.expenses import ExpenseService
from app.services.sheets import SheetsService


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Importa gastos históricos desde Google Sheets a la base de datos."
    )
    parser.add_argument("--phone", help="Importa solo el teléfono indicado.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula la importación sin escribir en la base.",
    )
    args = parser.parse_args()

    sheets_service = SheetsService()
    expense_service = ExpenseService()
    report = await expense_service.import_from_sheets(
        sheets_service,
        phone=args.phone,
        dry_run=args.dry_run,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
