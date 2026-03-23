from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.liabilities import LiabilityService


def _session_maker(session):
    maker = MagicMock()
    maker.return_value.__aenter__.return_value = session
    return maker


@pytest.mark.asyncio
async def test_create_liability_persists_record():
    session = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock(side_effect=lambda liability: setattr(liability, "id", 7))
    service = LiabilityService(session_maker=_session_maker(session))

    with patch(
        "app.services.liabilities.get_or_create_user",
        new=AsyncMock(return_value=SimpleNamespace(id=1)),
    ):
        result = await service.create_liability(
            "5491112345678",
            kind="installment",
            description="Notebook",
            monthly_amount=50000,
            remaining_periods=6,
        )

    assert result["success"] is True
    assert result["liability_id"] == 7
    assert result["formatted_confirmation"] == (
        "✅ Registré la obligación: *Notebook*\n"
        "- Cuotas restantes: 6\n"
        "- Monto mensual: *$50.000*"
    )
    session.add.assert_called_once()


@pytest.mark.asyncio
async def test_get_monthly_commitment_only_counts_active_liabilities():
    session = MagicMock()
    session.execute = AsyncMock(side_effect=[
        MagicMock(scalar_one_or_none=MagicMock(return_value=SimpleNamespace(id=1))),
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[
            SimpleNamespace(id=1, kind="installment", description="Notebook", monthly_amount=50000.0, remaining_periods=6, currency="ARS"),
            SimpleNamespace(id=2, kind="debt", description="Préstamo", monthly_amount=20000.0, remaining_periods=3, currency="ARS"),
        ])))),
    ])
    service = LiabilityService(session_maker=_session_maker(session))

    result = await service.get_monthly_commitment("5491112345678")

    assert result["success"] is True
    assert result["total_monthly_commitment"] == 70000.0
    assert result["total_remaining_commitment"] == 360000.0


@pytest.mark.asyncio
async def test_close_liability_rejects_missing_record():
    session = MagicMock()
    session.execute = AsyncMock(side_effect=[
        MagicMock(scalar_one_or_none=MagicMock(return_value=SimpleNamespace(id=1))),
        MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
    ])
    service = LiabilityService(session_maker=_session_maker(session))

    result = await service.close_liability("5491112345678", liability_id=99)

    assert result["success"] is False


@pytest.mark.asyncio
async def test_close_liability_succeeds_for_active_record():
    session = MagicMock()
    session.commit = AsyncMock()
    liability = SimpleNamespace(id=7, status="active", remaining_periods=4)
    session.execute = AsyncMock(side_effect=[
        MagicMock(scalar_one_or_none=MagicMock(return_value=SimpleNamespace(id=1))),
        MagicMock(scalar_one_or_none=MagicMock(return_value=liability)),
    ])
    service = LiabilityService(session_maker=_session_maker(session))

    result = await service.close_liability("5491112345678", liability_id=7)

    assert result == {"success": True, "liability_id": 7, "status": "closed"}
    assert liability.status == "closed"
    assert liability.remaining_periods == 0
    session.commit.assert_awaited_once()
