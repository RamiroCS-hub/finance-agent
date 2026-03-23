from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.alerts import AlertService


def _session_maker(session):
    maker = MagicMock()
    maker.return_value.__aenter__.return_value = session
    return maker


@pytest.mark.asyncio
async def test_evaluate_expense_alerts_detects_budget_exceeded_and_spike():
    session = MagicMock()
    session.execute = AsyncMock(side_effect=[
        MagicMock(scalar_one_or_none=MagicMock(return_value=SimpleNamespace(id=1))),
        MagicMock(scalar_one_or_none=MagicMock(return_value=SimpleNamespace(limit_amount=1000.0))),
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[
            SimpleNamespace(amount=700.0),
            SimpleNamespace(amount=500.0),
        ])))),
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[
            SimpleNamespace(amount=1500.0),
            SimpleNamespace(amount=300.0),
            SimpleNamespace(amount=280.0),
            SimpleNamespace(amount=260.0),
        ])))),
    ])
    service = AlertService(session_maker=_session_maker(session))

    alerts = await service.evaluate_expense_alerts(
        phone="5491112345678",
        amount=1500.0,
        category="Comida",
        spent_at=datetime(2026, 3, 21, 13, 0),
    )

    types = {alert["type"] for alert in alerts}
    assert "budget_exceeded" in types
    assert "spike_detected" in types
