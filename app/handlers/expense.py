from __future__ import annotations

import logging

from app.models.expense import ParsedExpense
from app.services import whatsapp
from app.services.sheets import SheetsService

logger = logging.getLogger(__name__)


async def register_expense(
    phone: str, expense: ParsedExpense, sheets: SheetsService
) -> None:
    """Registra el gasto en el sheet y responde al usuario."""
    success = sheets.append_expense(phone, expense)

    if success:
        msg = f"*Registrado:* ${expense.amount:,.2f} {expense.currency} — {expense.description} ({expense.category})"
        if expense.calculation:
            msg += f"\n_Cálculo: {expense.calculation}_"
    else:
        msg = (
            f"Hubo un error guardando tu gasto.\n"
            f"Tu gasto era: ${expense.amount:,.2f} {expense.currency} — {expense.description}\n"
            f"Intentá de nuevo en unos minutos."
        )

    await whatsapp.send_text(phone, msg)
