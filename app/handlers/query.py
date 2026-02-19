from __future__ import annotations

import logging
from datetime import datetime

from app.services import whatsapp
from app.services.sheets import SheetsService

logger = logging.getLogger(__name__)


async def get_monthly_summary(phone: str, sheets: SheetsService) -> None:
    """Envía el resumen del mes actual."""
    now = datetime.now()
    total = sheets.get_monthly_total(phone, now.month, now.year)
    categories = sheets.get_category_totals(phone, now.month, now.year)

    month_name = now.strftime("%B %Y").capitalize()

    if total == 0:
        await whatsapp.send_text(phone, f"No tenés gastos registrados en {month_name}.")
        return

    lines = [f"*Resumen {month_name}:*", f"*Total: ${total:,.2f}*", "─────────────"]
    for cat, amount in sorted(categories.items(), key=lambda x: x[1], reverse=True):
        pct = (amount / total) * 100 if total > 0 else 0
        lines.append(f"  {cat}: ${amount:,.2f} ({pct:.1f}%)")

    await whatsapp.send_text(phone, "\n".join(lines))


async def get_category_breakdown(phone: str, sheets: SheetsService) -> None:
    """Envía el desglose detallado por categoría."""
    now = datetime.now()
    categories = sheets.get_category_totals(phone, now.month, now.year)

    if not categories:
        await whatsapp.send_text(phone, "No tenés gastos este mes.")
        return

    month_name = now.strftime("%B %Y").capitalize()
    lines = [f"*Desglose por categoría — {month_name}:*", ""]
    for cat, amount in sorted(categories.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"  *{cat}*: ${amount:,.2f}")

    await whatsapp.send_text(phone, "\n".join(lines))


async def get_recent_expenses(phone: str, sheets: SheetsService) -> None:
    """Envía los últimos 10 gastos."""
    expenses = sheets.get_recent_expenses(phone, n=10)

    if not expenses:
        await whatsapp.send_text(phone, "No tenés gastos registrados.")
        return

    lines = ["*Últimos gastos:*", ""]
    for e in expenses:
        lines.append(
            f"  {e['fecha']} — ${e['monto']:,.2f} {e['moneda']} — {e['descripcion']} ({e['categoria']})"
        )

    await whatsapp.send_text(phone, "\n".join(lines))


async def send_sheet_link(phone: str, sheets: SheetsService) -> None:
    """Envía el link al spreadsheet."""
    url = sheets.get_sheet_url()
    await whatsapp.send_text(
        phone,
        f"*Tu planilla de gastos:*\n{url}\n\n_Buscá la hoja con tu número para ver tus datos._",
    )
