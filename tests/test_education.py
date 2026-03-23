from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.education import EducationService


def _session_maker(session):
    maker = MagicMock()
    maker.return_value.__aenter__.return_value = session
    return maker


@pytest.mark.asyncio
async def test_evaluate_financial_education_returns_benchmark_and_fund():
    session = MagicMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=SimpleNamespace(id=1)))
    )
    service = EducationService(session_maker=_session_maker(session))
    service._load_recent_expenses = AsyncMock(
        return_value=[
            SimpleNamespace(amount=50000.0, category="Supermercado", spent_at=datetime(2026, 1, 1, tzinfo=timezone.utc)),
            SimpleNamespace(amount=20000.0, category="Transporte", spent_at=datetime(2026, 1, 2, tzinfo=timezone.utc)),
            SimpleNamespace(amount=30000.0, category="Comida", spent_at=datetime(2026, 2, 1, tzinfo=timezone.utc)),
            SimpleNamespace(amount=15000.0, category="Entretenimiento", spent_at=datetime(2026, 2, 2, tzinfo=timezone.utc)),
            SimpleNamespace(amount=25000.0, category="Hogar", spent_at=datetime(2026, 3, 1, tzinfo=timezone.utc)),
        ]
    )
    service.insights_service.detect_spending_leaks = AsyncMock(
        return_value={"status": "ok", "insights": []}
    )
    service.insights_service.compare_spending_periods = AsyncMock(
        return_value={"status": "insufficient_data"}
    )

    result = await service.evaluate_financial_education("5491112345678")

    assert result["status"] == "ok"
    assert result["benchmark_50_30_20"]["average_monthly_spend"] > 0
    assert result["emergency_fund"]["recommended_min"] > 0


@pytest.mark.asyncio
async def test_evaluate_financial_education_falls_back_without_inflation():
    session = MagicMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=SimpleNamespace(id=1)))
    )
    service = EducationService(session_maker=_session_maker(session))
    service._load_recent_expenses = AsyncMock(
        return_value=[
            SimpleNamespace(amount=50000.0, category="Supermercado", spent_at=datetime(2026, 1, 1, tzinfo=timezone.utc)),
            SimpleNamespace(amount=20000.0, category="Transporte", spent_at=datetime(2026, 1, 2, tzinfo=timezone.utc)),
            SimpleNamespace(amount=30000.0, category="Comida", spent_at=datetime(2026, 2, 1, tzinfo=timezone.utc)),
            SimpleNamespace(amount=15000.0, category="Entretenimiento", spent_at=datetime(2026, 2, 2, tzinfo=timezone.utc)),
            SimpleNamespace(amount=25000.0, category="Hogar", spent_at=datetime(2026, 3, 1, tzinfo=timezone.utc)),
        ]
    )
    service.insights_service.detect_spending_leaks = AsyncMock(
        return_value={"status": "ok", "insights": []}
    )

    with patch("app.services.education.settings.MONTHLY_INFLATION_RATE", 0.0):
        result = await service.evaluate_financial_education("5491112345678")

    assert result["inflation_adjusted_comparison"]["status"] == "nominal_only"


@pytest.mark.asyncio
async def test_evaluate_financial_education_uses_configured_inflation_rate():
    session = MagicMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=SimpleNamespace(id=1)))
    )
    service = EducationService(session_maker=_session_maker(session))
    service._load_recent_expenses = AsyncMock(
        return_value=[
            SimpleNamespace(amount=50000.0, category="Supermercado", spent_at=datetime(2026, 1, 1, tzinfo=timezone.utc)),
            SimpleNamespace(amount=20000.0, category="Transporte", spent_at=datetime(2026, 1, 2, tzinfo=timezone.utc)),
            SimpleNamespace(amount=30000.0, category="Comida", spent_at=datetime(2026, 2, 1, tzinfo=timezone.utc)),
            SimpleNamespace(amount=15000.0, category="Entretenimiento", spent_at=datetime(2026, 2, 2, tzinfo=timezone.utc)),
            SimpleNamespace(amount=25000.0, category="Hogar", spent_at=datetime(2026, 3, 1, tzinfo=timezone.utc)),
        ]
    )
    service.insights_service.detect_spending_leaks = AsyncMock(
        return_value={"status": "ok", "insights": []}
    )
    service.insights_service.compare_spending_periods = AsyncMock(
        return_value={
            "status": "ok",
            "current_total": 120000.0,
            "previous_total": 100000.0,
        }
    )

    with patch("app.services.education.settings.MONTHLY_INFLATION_RATE", 0.1):
        result = await service.evaluate_financial_education("5491112345678")

    assert result["inflation_adjusted_comparison"]["status"] == "ok"
    assert "real" in result["inflation_adjusted_comparison"]["message"].lower()


@pytest.mark.asyncio
async def test_generate_personalized_tips_uses_real_patterns():
    service = EducationService(session_maker=_session_maker(MagicMock()))
    service.insights_service.detect_spending_leaks = AsyncMock(
        return_value={
            "status": "ok",
            "insights": [
                {
                    "type": "repetitive_merchant",
                    "merchant": "Starbucks",
                    "impact_amount": 12000.0,
                }
            ],
        }
    )

    tips = await service.generate_personalized_tips(
        "5491112345678",
        benchmark={"wants_ratio": 40.0, "average_monthly_spend": 100000.0},
    )

    assert len(tips) == 2
    assert "Starbucks" in tips[1]["message"]
