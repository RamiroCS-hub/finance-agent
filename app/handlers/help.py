from __future__ import annotations

from app.services import whatsapp

HELP_MESSAGE = """*Bot de Gastos*

*Registrar un gasto:*
  "500 almuerzo"
  "$1200 uber"
  "3 cervezas a 1500 c/u"
  "10 USD menos 22% de IVA"

*Consultas:*
  "resumen" — Total del mes actual
  "categorías" — Desglose por categoría
  "últimos" — Últimos 10 gastos
  "link" — Link a tu planilla

  "ayuda" — Este mensaje"""


async def send_help(phone: str) -> None:
    await whatsapp.send_text(phone, HELP_MESSAGE)
