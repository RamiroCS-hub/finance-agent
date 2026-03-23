from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from app.services.insights import SpendingInsightsService


def _session_maker(session):
    maker = MagicMock()
    maker.return_value.__aenter__.return_value = session
    return maker


@pytest.mark.asyncio
async def test_compare_spending_periods_returns_ranked_changes():
    session = MagicMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=SimpleNamespace(id=1)))
    )
    service = SpendingInsightsService(session_maker=_session_maker(session))
    service._load_expenses_between = AsyncMock(
        side_effect=[
            [
                SimpleNamespace(category="Comida", amount=5000.0, description="super", shop="Coto"),
                SimpleNamespace(category="Transporte", amount=1000.0, description="uber", shop=None),
            ],
            [
                SimpleNamespace(category="Comida", amount=3000.0, description="super", shop="Coto"),
                SimpleNamespace(category="Transporte", amount=1800.0, description="uber", shop=None),
            ],
        ]
    )

    with patch(
        "app.services.insights.local_now_for_phone",
        return_value=datetime(2026, 3, 21, 12, 0, tzinfo=ZoneInfo("America/Argentina/Buenos_Aires")),
    ):
        result = await service.compare_spending_periods("5491112345678")

    assert result["status"] == "ok"
    assert result["changes"][0]["key"] == "Comida"
    assert result["changes"][0]["delta"] == 2000.0


@pytest.mark.asyncio
async def test_compare_spending_periods_handles_insufficient_history():
    session = MagicMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=SimpleNamespace(id=1)))
    )
    service = SpendingInsightsService(session_maker=_session_maker(session))
    service._load_expenses_between = AsyncMock(side_effect=[[SimpleNamespace(category="Comida", amount=1000.0)], []])

    with patch(
        "app.services.insights.local_now_for_phone",
        return_value=datetime(2026, 3, 21, 12, 0, tzinfo=ZoneInfo("America/Argentina/Buenos_Aires")),
    ):
        result = await service.compare_spending_periods("5491112345678")

    assert result["status"] == "insufficient_data"


@pytest.mark.asyncio
async def test_detect_spending_leaks_returns_repetitive_and_growth_insights():
    session = MagicMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=SimpleNamespace(id=1)))
    )
    service = SpendingInsightsService(session_maker=_session_maker(session))
    service._load_expenses_between = AsyncMock(
        return_value=[
            SimpleNamespace(amount=2400.0, description="cafe", shop="Starbucks"),
            SimpleNamespace(amount=2200.0, description="cafe", shop="Starbucks"),
            SimpleNamespace(amount=2100.0, description="cafe", shop="Starbucks"),
            SimpleNamespace(amount=8000.0, description="super", shop="Coto"),
        ]
    )
    service.compare_spending_periods = AsyncMock(
        return_value={
            "status": "ok",
            "previous_label": "2026-02",
            "changes": [
                {
                    "key": "Comida",
                    "delta": 3500.0,
                    "current_total": 12000.0,
                }
            ],
        }
    )

    with patch(
        "app.services.insights.local_now_for_phone",
        return_value=datetime(2026, 3, 21, 12, 0, tzinfo=ZoneInfo("America/Argentina/Buenos_Aires")),
    ):
        result = await service.detect_spending_leaks("5491112345678")

    assert result["status"] == "ok"
    insight_types = {insight["type"] for insight in result["insights"]}
    assert "category_growth" in insight_types
    assert "repetitive_merchant" in insight_types
