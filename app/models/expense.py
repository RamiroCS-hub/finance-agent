from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class ParsedExpense:
    amount: float
    description: str
    category: str
    currency: str
    raw_message: str
    shop: Optional[str] = None
    spent_at: Optional[datetime] = None
    source_timezone: Optional[str] = None
    calculation: Optional[str] = None
    source: str = "llm"  # "llm" o "regex"
    original_amount: Optional[float] = None  # Monto antes de conversión
    original_currency: Optional[str] = None  # Moneda original si fue convertida
