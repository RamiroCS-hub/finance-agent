from __future__ import annotations

import logging

from app.handlers import expense as expense_handler
from app.handlers import help as help_handler
from app.handlers import query as query_handler
from app.services.llm_provider import LLMProvider
from app.services.parser import parse_message
from app.services.sheets import SheetsService

logger = logging.getLogger(__name__)

INTENT_KEYWORDS: dict[str, list[str]] = {
    "summary": ["resumen", "total", "cuánto gasté", "cuanto gaste", "cuanto llevo"],
    "categories": ["por categoría", "por categoria", "categorías", "categorias", "desglose"],
    "recent": ["últimos", "ultimos", "recientes", "historial"],
    "help": ["ayuda", "help", "?", "comandos", "menu"],
    "link": ["link", "planilla", "sheet", "excel"],
}


def _detect_intent(message: str) -> str | None:
    """Detecta la intención del mensaje por keywords. Retorna None si no matchea."""
    msg_lower = message.strip().lower()
    for intent, keywords in INTENT_KEYWORDS.items():
        if any(kw in msg_lower for kw in keywords):
            return intent
    return None


async def route_message(
    phone: str,
    message: str,
    llm: LLMProvider,
    sheets: SheetsService | None,
) -> None:
    """Punto de entrada principal: recibe un mensaje y lo despacha al handler correcto."""
    from app.services import whatsapp

    # Si Google Sheets no está disponible, avisar y cortar
    if sheets is None:
        await whatsapp.send_text(
            phone,
            "El bot está activo pero Google Sheets no está configurado. "
            "Contactá al administrador.",
        )
        return

    # Asegurar que el usuario existe
    is_new = sheets.ensure_user(phone)
    if is_new:
        logger.info("Nuevo usuario: %s", phone)

    # Detectar intención por keywords primero (rápido, sin LLM)
    intent = _detect_intent(message)

    if intent == "summary":
        await query_handler.get_monthly_summary(phone, sheets)
        return
    if intent == "categories":
        await query_handler.get_category_breakdown(phone, sheets)
        return
    if intent == "recent":
        await query_handler.get_recent_expenses(phone, sheets)
        return
    if intent == "help":
        await help_handler.send_help(phone)
        return
    if intent == "link":
        await query_handler.send_sheet_link(phone, sheets)
        return

    # Si no es un comando, intentar parsear como gasto
    parsed = await parse_message(llm, message)
    if parsed is not None:
        await expense_handler.register_expense(phone, parsed, sheets)
        return

    # No se pudo interpretar
    await help_handler.send_help(phone)
