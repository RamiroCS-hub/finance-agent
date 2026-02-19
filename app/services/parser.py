from __future__ import annotations

import json
import logging
import re
from datetime import datetime

from app.config import settings
from app.models.expense import ParsedExpense
from app.services.llm_provider import LLMProvider

logger = logging.getLogger(__name__)

CATEGORIES = [
    "Comida",
    "Transporte",
    "Supermercado",
    "Servicios",
    "Entretenimiento",
    "Salud",
    "Ropa",
    "Educación",
    "Hogar",
    "Otros",
]

SYSTEM_PROMPT = """Sos un asistente que interpreta mensajes de gastos. El usuario te envía un mensaje de texto
describiendo un gasto y vos debés extraer la información estructurada.

REGLAS:
1. Extraé el monto FINAL del gasto, resolviendo cualquier operación matemática.
   Ejemplos: "10 menos 22%" = 7.80, "3 cervezas a 1500 c/u" = 4500, "mitad de 12000" = 6000.
2. Categorizá el gasto en UNA de estas categorías: {categories}.
3. Moneda por defecto: {currency}. Solo usá otra moneda si el usuario la menciona explícitamente
   (ej: "dólares", "USD", "euros", "EUR").
4. Si hubo un cálculo, incluí el detalle en "calculation".
5. Respondé SOLO con JSON válido, sin texto adicional.

Formato de respuesta:
{{
  "amount": <número>,
  "description": "<descripción corta del gasto>",
  "category": "<categoría>",
  "currency": "<código ISO 3 letras>",
  "calculation": "<detalle del cálculo o null>"
}}

Si el mensaje NO es un gasto (es una pregunta, saludo, o comando), respondé:
{{ "is_expense": false }}
"""


async def parse_with_llm(
    llm: LLMProvider, message: str, default_currency: str
) -> ParsedExpense | None:
    """Intenta parsear el mensaje usando el LLM."""
    prompt = SYSTEM_PROMPT.format(
        categories=", ".join(CATEGORIES),
        currency=default_currency,
    )

    raw = await llm.complete(prompt, message)
    data = json.loads(raw)

    if data.get("is_expense") is False:
        return None

    return ParsedExpense(
        amount=float(data["amount"]),
        description=data["description"],
        category=data["category"],
        currency=data.get("currency", default_currency),
        raw_message=message,
        calculation=data.get("calculation"),
        source="llm",
    )


# --- Regex Fallback ---

REGEX_PATTERNS = [
    # "500 almuerzo", "$1200 uber"
    re.compile(r"^\$?\s*([\d.,]+)\s+(.+)$", re.IGNORECASE),
    # "almuerzo 500", "uber $1200"
    re.compile(r"^(.+?)\s+\$?([\d.,]+)$", re.IGNORECASE),
    # "gasté 3500 en super"
    re.compile(
        r"^gast[eé]\s+\$?([\d.,]+)\s+(?:en\s+)?(.+)$", re.IGNORECASE
    ),
]

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "Comida": ["almuerzo", "cena", "desayuno", "restaurant", "comida", "cafe"],
    "Transporte": ["uber", "taxi", "nafta", "combustible", "subte", "bondi"],
    "Supermercado": ["super", "supermercado", "mercado", "compras"],
    "Servicios": ["luz", "gas", "agua", "internet", "telefono", "celular"],
    "Entretenimiento": ["cine", "netflix", "spotify", "salida", "bar", "cerveza"],
    "Salud": ["farmacia", "medico", "obra social", "remedio"],
    "Ropa": ["ropa", "zapatillas", "campera", "remera", "pantalon"],
    "Educación": ["libro", "curso", "clase", "universidad"],
    "Hogar": ["alquiler", "expensas", "limpieza", "mueble"],
}


def _clean_amount(raw: str) -> float | None:
    cleaned = raw.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _categorize_by_keywords(description: str) -> str:
    desc_lower = description.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in desc_lower for kw in keywords):
            return category
    return "Otros"


def parse_with_regex(message: str, default_currency: str) -> ParsedExpense | None:
    """Fallback: intenta parsear el mensaje con regex básicos."""
    for pattern in REGEX_PATTERNS:
        match = pattern.match(message.strip())
        if not match:
            continue

        groups = match.groups()
        # Determinar cuál grupo es el monto y cuál la descripción
        try:
            amount = _clean_amount(groups[0])
            description = groups[1].strip()
        except (ValueError, IndexError):
            try:
                amount = _clean_amount(groups[1])
                description = groups[0].strip()
            except (ValueError, IndexError):
                continue

        if amount is None or amount <= 0:
            continue

        return ParsedExpense(
            amount=amount,
            description=description,
            category=_categorize_by_keywords(description),
            currency=default_currency,
            raw_message=message,
            calculation=None,
            source="regex",
        )

    return None


async def parse_message(
    llm: LLMProvider, message: str, default_currency: str | None = None
) -> ParsedExpense | None:
    """
    Parser principal: LLM-first con regex fallback.
    Retorna None si el mensaje no es un gasto.
    """
    currency = default_currency or settings.DEFAULT_CURRENCY

    # Intento 1: LLM
    try:
        result = await parse_with_llm(llm, message, currency)
        if result is not None:
            logger.info("Gasto parseado por LLM: %s", result)
            return result
        # LLM dijo que no es un gasto
        return None
    except Exception as e:
        logger.warning("LLM parser falló (%s), usando regex fallback", e)

    # Intento 2: Regex fallback
    result = parse_with_regex(message, currency)
    if result is not None:
        logger.info("Gasto parseado por regex fallback: %s", result)
    return result
