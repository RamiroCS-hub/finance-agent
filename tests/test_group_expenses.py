from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.group_expenses import (
    BalanceRow,
    GroupExpenseService,
    minimize_settlements,
    split_amount_evenly,
)


def _session_maker(session):
    maker = MagicMock()
    maker.return_value.__aenter__.return_value = session
    return maker


def test_split_amount_evenly_handles_remainder():
    assert split_amount_evenly(100, 3) == [33.34, 33.33, 33.33]


def test_minimize_settlements_returns_minimal_transfers():
    rows = [
        BalanceRow(phone="A", paid=100.0, owes=25.0),
        BalanceRow(phone="B", paid=0.0, owes=25.0),
        BalanceRow(phone="C", paid=0.0, owes=50.0),
    ]

    transfers = minimize_settlements(rows)

    assert transfers == [
        {"from": "B", "to": "A", "amount": 25.0},
        {"from": "C", "to": "A", "amount": 50.0},
    ]


@pytest.mark.asyncio
async def test_register_group_expense_creates_group_ledger():
    session = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, "id", 77))
    service = GroupExpenseService(session_maker=_session_maker(session))

    payer = SimpleNamespace(id=1, whatsapp_number="549111")
    participant = SimpleNamespace(id=2, whatsapp_number="549222")
    group = SimpleNamespace(id=5, whatsapp_group_id="grp-1")

    with patch(
        "app.services.group_expenses.ensure_group_member",
        new=AsyncMock(return_value=(group, payer, SimpleNamespace())),
    ), patch.object(
        service,
        "_resolve_participants",
        new=AsyncMock(return_value=[payer, participant]),
    ):
        result = await service.register_group_expense(
            whatsapp_group_id="grp-1",
            payer_phone="549111",
            amount=100.0,
            description="super",
        )

    assert result["success"] is True
    assert result["group_expense_id"] == 77
    assert result["participants"] == ["549111", "549222"]
    assert result["shares"] == [50.0, 50.0]
    assert session.add.call_count == 3
