from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.expense import ParsedExpense
from app.services.expenses import ExpenseService


def _session_maker(session):
    maker = MagicMock()
    maker.return_value.__aenter__.return_value = session
    return maker


@pytest.mark.asyncio
async def test_append_expense_persists_and_returns_expense():
    session = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    service = ExpenseService(session_maker=_session_maker(session))
    user = SimpleNamespace(id=7)

    async def fake_refresh(expense):
        expense.id = 99

    session.refresh.side_effect = fake_refresh

    with patch("app.services.expenses.get_or_create_user", new=AsyncMock(return_value=user)):
        result = await service.append_expense(
            "5491123456789",
            ParsedExpense(
                amount=850.0,
                description="farmacia",
                category="Salud",
                currency="ARS",
                raw_message="850 farmacia",
                shop="Farmacity",
            ),
        )

    assert result is not None
    assert result.id == 99
    assert result.user_id == 7
    assert result.shop == "Farmacity"
    session.add.assert_called_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_last_expense_returns_serialized_payload():
    session = MagicMock()
    session.commit = AsyncMock()
    session.delete = AsyncMock()
    session.execute = AsyncMock()
    service = ExpenseService(session_maker=_session_maker(session))
    service._get_user = AsyncMock(return_value=SimpleNamespace(id=3))
    expense = SimpleNamespace(
        id=55,
        spent_at=datetime(2026, 3, 21, 13, 30, tzinfo=timezone.utc),
        amount=1200.0,
        currency="ARS",
        description="super",
        category="Comida",
    )
    session.execute.return_value = MagicMock(
        scalar_one_or_none=MagicMock(return_value=expense)
    )

    result = await service.delete_last_expense("5491123456789")

    assert result == {
        "expense_id": 55,
        "fecha": "2026-03-21",
        "hora": "10:30",
        "monto": 1200.0,
        "moneda": "ARS",
        "shop": None,
        "source_timezone": None,
        "descripcion": "super",
        "categoria": "Comida",
    }
    session.delete.assert_awaited_once_with(expense)
    session.commit.assert_awaited_once()
