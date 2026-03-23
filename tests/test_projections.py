from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.projections import SavingsProjectionService


def _session_maker(session):
    maker = MagicMock()
    maker.return_value.__aenter__.return_value = session
    return maker


@pytest.mark.asyncio
async def test_project_savings_manual_weekly_projection():
    service = SavingsProjectionService(session_maker=_session_maker(MagicMock()))
    service._get_user = AsyncMock(return_value=None)

    result = await service.project_savings(
        "5491112345678",
        amount=10000,
        frequency="weekly",
        horizon_months=6,
    )

    assert result["status"] == "ok"
    assert result["source"] == "manual"
    assert result["projected_savings"] == 240000.0


@pytest.mark.asyncio
async def test_project_savings_historical_projection_with_goal_impact():
    session = MagicMock()
    service = SavingsProjectionService(session_maker=_session_maker(session))
    service._get_user = AsyncMock(return_value=SimpleNamespace(id=1))
    service._get_active_goal = AsyncMock(
        return_value=SimpleNamespace(target_amount=100000.0, current_amount=25000.0)
    )
    service._historical_average_for_category = AsyncMock(return_value=40000.0)

    result = await service.project_savings(
        "5491112345678",
        category="Comida",
        reduction_percent=25,
        frequency="monthly",
        horizon_months=6,
    )

    assert result["status"] == "ok"
    assert result["source"] == "historical"
    assert result["periodic_saving"] == 10000.0
    assert result["goal_impact"]["projected_total"] == 85000.0


@pytest.mark.asyncio
async def test_project_savings_requests_clarification_when_missing_inputs():
    service = SavingsProjectionService(session_maker=_session_maker(MagicMock()))

    result = await service.project_savings("5491112345678", category="Comida")

    assert result["status"] == "needs_clarification"


@pytest.mark.asyncio
async def test_project_savings_handles_insufficient_history():
    session = MagicMock()
    service = SavingsProjectionService(session_maker=_session_maker(session))
    service._get_user = AsyncMock(return_value=SimpleNamespace(id=1))
    service._get_active_goal = AsyncMock(return_value=None)
    service._historical_average_for_category = AsyncMock(return_value=None)

    result = await service.project_savings(
        "5491112345678",
        category="Comida",
        reduction_percent=20,
        frequency="monthly",
    )

    assert result["status"] == "insufficient_data"
