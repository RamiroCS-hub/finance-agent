from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.budgets import BudgetService


def _session_maker(session):
    maker = MagicMock()
    maker.return_value.__aenter__.return_value = session
    return maker


@pytest.mark.asyncio
async def test_save_budget_creates_rule():
    session = MagicMock()
    session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    session.commit = AsyncMock()
    service = BudgetService(session_maker=_session_maker(session))

    with patch("app.services.budgets.get_or_create_user", new=AsyncMock(return_value=SimpleNamespace(id=1))):
        result = await service.save_budget("5491112345678", "Comida", 200000)

    assert result["status"] == "created"
    assert session.add.called
    assert session.commit.called


@pytest.mark.asyncio
async def test_list_budgets_returns_serialized_rules():
    session = MagicMock()
    session.execute = AsyncMock(side_effect=[
        MagicMock(scalar_one_or_none=MagicMock(return_value=SimpleNamespace(id=1))),
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[
            SimpleNamespace(category="Comida", period="monthly", limit_amount=200000),
        ])))),
    ])
    service = BudgetService(session_maker=_session_maker(session))

    result = await service.list_budgets("5491112345678")

    assert result == [{"category": "Comida", "period": "monthly", "limit_amount": 200000.0}]
