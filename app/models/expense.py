from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ParsedExpense:
    amount: float
    description: str
    category: str
    currency: str
    raw_message: str
    calculation: Optional[str] = None
    source: str = "llm"  # "llm" o "regex"
