from __future__ import annotations

import json
import logging
import re
from typing import Any

from google import genai

from app.config import settings

logger = logging.getLogger(__name__)

_CATEGORY_KEYWORDS = {
    "Supermercado": ["super", "market", "carrefour", "coto", "disco", "jumbo"],
    "Comida": ["cafe", "bar", "burger", "pizza", "restaurant", "resto", "mc", "starbucks"],
    "Transporte": ["uber", "cabify", "taxi", "ypf", "shell", "axion"],
    "Salud": ["farm", "dr", "clinica", "hospital"],
}


def normalize_receipt_payload(raw_payload: dict[str, Any]) -> dict[str, Any]:
    amount = _parse_amount(raw_payload.get("amount"))
    shop = _clean_text(raw_payload.get("shop"))
    category = _clean_text(raw_payload.get("category")) or _guess_category(shop)
    confidence = _parse_confidence(raw_payload.get("confidence"))
    detected_text = _clean_text(raw_payload.get("detected_text"))

    if amount is None:
        confidence = min(confidence, 0.35)
    if not shop:
        confidence = min(confidence, 0.7)

    if amount is not None and shop and confidence >= settings.RECEIPT_OCR_AUTO_CONFIDENCE:
        status = "high_confidence"
    elif amount is not None and confidence >= settings.RECEIPT_OCR_CONFIRM_CONFIDENCE:
        status = "needs_confirmation"
    else:
        status = "low_confidence"

    return {
        "amount": amount,
        "shop": shop,
        "category": category or "Otros",
        "confidence": round(confidence, 2),
        "detected_text": detected_text,
        "status": status,
    }


async def extract_receipt_fields(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
) -> dict[str, Any]:
    provider = settings.RECEIPT_OCR_PROVIDER.lower()
    if provider != "gemini":
        raise ValueError(f"Proveedor OCR no soportado: {settings.RECEIPT_OCR_PROVIDER}")
    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY no está configurada para OCR")

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    model = settings.RECEIPT_OCR_MODEL or settings.GEMINI_MODEL
    prompt = (
        "Extraé datos de este ticket o comprobante. "
        "Respondé SOLO JSON con las claves: amount, shop, category, confidence, detected_text. "
        "amount debe ser un número. confidence debe ser un número entre 0 y 1. "
        "Si algo no se ve, devolvelo null."
    )
    response = client.models.generate_content(
        model=model,
        contents=[
            prompt,
            genai.types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
        ],
        config=genai.types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
        ),
    )
    return json.loads(response.text or "{}")


async def extract_receipt_candidate(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
) -> dict[str, Any]:
    try:
        raw_payload = await extract_receipt_fields(image_bytes, mime_type=mime_type)
        candidate = normalize_receipt_payload(raw_payload)
        candidate["raw_payload"] = raw_payload
        return candidate
    except Exception as exc:
        logger.error("Error extrayendo ticket por OCR: %s", exc)
        return {
            "amount": None,
            "shop": None,
            "category": "Otros",
            "confidence": 0.0,
            "detected_text": "",
            "status": "error",
            "error": str(exc),
        }


def _parse_amount(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None

    cleaned = value.strip()
    cleaned = re.sub(r"[^\d,.-]", "", cleaned)
    if not cleaned:
        return None

    if cleaned.count(",") == 1 and cleaned.count(".") == 1:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif cleaned.count(",") == 1 and cleaned.count(".") > 1:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif cleaned.count(",") == 1 and cleaned.count(".") == 0:
        cleaned = cleaned.replace(",", ".")
    elif cleaned.count(".") > 1:
        cleaned = cleaned.replace(".", "")

    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = 0.0
    return max(0.0, min(confidence, 1.0))


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _guess_category(shop: str | None) -> str | None:
    if not shop:
        return None
    lower_shop = shop.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(keyword in lower_shop for keyword in keywords):
            return category
    return None
