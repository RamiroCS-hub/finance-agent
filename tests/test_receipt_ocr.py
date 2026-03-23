from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.receipt_ocr import (
    extract_receipt_candidate,
    extract_receipt_fields,
    normalize_receipt_payload,
)


def test_normalize_receipt_payload_high_confidence():
    payload = normalize_receipt_payload(
        {
            "amount": "12.345,50",
            "shop": "Coto",
            "category": None,
            "confidence": 0.92,
            "detected_text": "TOTAL 12.345,50 COTO",
        }
    )

    assert payload["amount"] == 12345.50
    assert payload["shop"] == "Coto"
    assert payload["category"] == "Supermercado"
    assert payload["status"] == "high_confidence"


def test_normalize_receipt_payload_needs_confirmation_without_shop():
    payload = normalize_receipt_payload(
        {
            "amount": 2500,
            "shop": None,
            "confidence": 0.75,
        }
    )

    assert payload["amount"] == 2500.0
    assert payload["status"] == "needs_confirmation"


@pytest.mark.asyncio
async def test_extract_receipt_fields_uses_gemini():
    mock_response = MagicMock()
    mock_response.text = '{"amount": 1500, "shop": "Farmacity", "category": "Salud", "confidence": 0.91}'

    with patch("app.services.receipt_ocr.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        mock_client_cls.return_value = mock_client
        with patch("app.services.receipt_ocr.settings.GEMINI_API_KEY", "fake-key"):
            with patch("app.services.receipt_ocr.settings.GEMINI_MODEL", "gemini-2.0-flash"):
                result = await extract_receipt_fields(b"image-bytes", mime_type="image/jpeg")

    assert result["shop"] == "Farmacity"
    mock_client.models.generate_content.assert_called_once()


@pytest.mark.asyncio
async def test_extract_receipt_candidate_returns_error_payload_on_failure():
    with patch(
        "app.services.receipt_ocr.extract_receipt_fields",
        side_effect=RuntimeError("ocr down"),
    ):
        result = await extract_receipt_candidate(b"image-bytes")

    assert result["status"] == "error"
    assert "ocr down" in result["error"]
