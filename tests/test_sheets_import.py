from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.expenses import ExpenseService


def _session_maker(session):
    maker = MagicMock()
    maker.return_value.__aenter__.return_value = session
    return maker


@pytest.mark.asyncio
async def test_import_from_sheets_skips_invalid_and_duplicates():
    session = MagicMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock()
    user = SimpleNamespace(id=1)
    service = ExpenseService(session_maker=_session_maker(session))

    duplicate_result = MagicMock()
    duplicate_result.scalar_one_or_none.return_value = 123
    missing_result = MagicMock()
    missing_result.scalar_one_or_none.return_value = None
    session.execute.side_effect = [duplicate_result, missing_result]

    sheets_service = MagicMock()
    sheets_service.list_user_phones.return_value = ["5491123456789"]
    sheets_service.export_expenses.return_value = [
        {
            "fecha": "2026-03-20",
            "hora": "10:00",
            "monto": "850",
            "moneda": "ARS",
            "descripcion": "uber",
            "categoria": "Transporte",
            "mensaje_original": "850 uber",
        },
        {
            "fecha": "bad-date",
            "hora": "10:00",
            "monto": "100",
            "moneda": "ARS",
            "descripcion": "broken",
            "categoria": "Otros",
            "mensaje_original": "100 broken",
        },
        {
            "fecha": "2026-03-21",
            "hora": "09:00",
            "monto": "500",
            "moneda": "ARS",
            "descripcion": "cafe",
            "categoria": "Comida",
            "mensaje_original": "500 cafe",
        },
    ]

    with patch("app.services.expenses.get_or_create_user", new=AsyncMock(return_value=user)):
        report = await service.import_from_sheets(sheets_service)

    assert report["processed"] == 3
    assert report["skipped_duplicates"] == 1
    assert report["skipped_invalid"] == 1
    assert report["imported"] == 1
    session.add.assert_called_once()
    session.commit.assert_awaited_once()
