"""
Tests para app/agent/tools.py.

Verifica que las herramientas de gastos hablen con el store de DB y mantengan
el formato observable esperado.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.tools import ToolRegistry
from app.models.agent import ToolDefinition
from app.services.plan_usage import QuotaDecision


@pytest.fixture
def mock_store():
    store = MagicMock()
    store.append_expense.return_value = SimpleNamespace(id=3, user_id=1)
    store.get_monthly_total.return_value = 5000.0
    store.get_category_totals.return_value = {"Comida": 2000.0, "Transporte": 3000.0}
    store.get_recent_expenses.return_value = [
        {
            "expense_id": 11,
            "fecha": "2026-02-19",
            "monto": 850.0,
            "descripcion": "uber",
            "categoria": "Transporte",
            "hora": "10:00",
            "moneda": "ARS",
        },
        {
            "expense_id": 10,
            "fecha": "2026-02-18",
            "monto": 500.0,
            "descripcion": "farmacia",
            "categoria": "Salud",
            "hora": "09:30",
            "moneda": "ARS",
        },
    ]
    store.search_expenses.return_value = [
        {
            "expense_id": 10,
            "fecha": "2026-02-18",
            "monto": 1200.0,
            "descripcion": "combo burger",
            "shop": "Burger Club",
            "categoria": "Comida",
            "hora": "09:30",
            "moneda": "ARS",
        },
        {
            "expense_id": 11,
            "fecha": "2026-02-19",
            "monto": 800.0,
            "descripcion": "uber centro",
            "shop": "Uber",
            "categoria": "Transporte",
            "hora": "10:00",
            "moneda": "ARS",
        },
        {
            "expense_id": 12,
            "fecha": "2026-02-20",
            "monto": 800.0,
            "descripcion": "uber vuelta",
            "shop": "Uber",
            "categoria": "Transporte",
            "hora": "21:30",
            "moneda": "ARS",
        },
        {
            "expense_id": 13,
            "fecha": "2026-02-21",
            "monto": 800.0,
            "descripcion": "almuerzo",
            "shop": "Burger Club",
            "categoria": "Comida",
            "hora": "13:15",
            "moneda": "ARS",
        },
    ]
    store.delete_last_expense.return_value = {
        "expense_id": 11,
        "fecha": "2026-02-19",
        "monto": 850.0,
        "descripcion": "uber",
        "categoria": "Transporte",
        "hora": "10:00",
        "moneda": "ARS",
    }
    return store


@pytest.fixture
def registry(mock_store):
    registry = ToolRegistry(mock_store, "5491123456789")
    registry.alert_service.evaluate_expense_alerts = AsyncMock(return_value=[])
    registry.budget_service.save_budget = AsyncMock(
        return_value={
            "status": "created",
            "category": "Comida",
            "period": "monthly",
            "limit_amount": 200000.0,
        }
    )
    registry.budget_service.list_budgets = AsyncMock(
        return_value=[{"category": "Comida", "period": "monthly", "limit_amount": 200000.0}]
    )
    registry.insights_service.compare_spending_periods = AsyncMock(
        return_value={"status": "ok", "changes": []}
    )
    registry.insights_service.detect_spending_leaks = AsyncMock(
        return_value={"status": "ok", "insights": []}
    )
    registry.projection_service.project_savings = AsyncMock(
        return_value={"status": "ok", "projected_savings": 60000.0}
    )
    registry.liability_service.create_liability = AsyncMock(
        return_value={"success": True, "liability_id": 8}
    )
    registry.liability_service.get_monthly_commitment = AsyncMock(
        return_value={"success": True, "total_monthly_commitment": 70000.0}
    )
    registry.liability_service.close_liability = AsyncMock(
        return_value={"success": True, "liability_id": 8, "status": "closed"}
    )
    registry.education_service.evaluate_financial_education = AsyncMock(
        return_value={"status": "ok", "tips": []}
    )
    return registry


class TestDefinitions:
    def test_returns_twenty_six_tools(self, registry):
        assert len(registry.definitions()) == 26

    def test_all_are_tool_definitions(self, registry):
        assert all(isinstance(tool, ToolDefinition) for tool in registry.definitions())

    def test_expected_tool_names(self, registry):
        names = {tool.name for tool in registry.definitions()}
        assert names == {
            "register_expense",
            "get_monthly_summary",
            "get_category_breakdown",
            "get_recent_expenses",
            "delete_last_expense",
            "search_expenses",
            "get_sheet_url",
            "calculate",
            "convert_currency",
            "send_cat_pic",
            "get_user_groups_info",
            "save_budget",
            "list_budgets",
            "get_spending_comparison",
            "get_spending_insights",
            "project_savings",
            "create_liability",
            "get_monthly_commitment",
            "close_liability",
            "get_financial_education",
            "register_group_expense",
            "get_group_balance",
            "settle_group_balances",
            "create_group_goal",
            "save_personality",
            "generate_expense_report",
        }


class TestRun:
    def test_unknown_tool_raises(self, registry):
        with pytest.raises(ValueError, match="desconocida"):
            registry.run("nonexistent_tool")

    def test_get_sheet_url_is_sync(self, registry):
        result = registry.run("get_sheet_url")
        assert result["available"] is False
        assert "planilla" in result["message"].lower()


class TestRegisterExpense:
    @pytest.fixture(autouse=True)
    def mock_db(self):
        session_instance = AsyncMock()
        session_instance.execute.return_value = MagicMock(
            scalar_one_or_none=MagicMock(return_value=None)
        )
        session_instance.commit = AsyncMock()

        with patch("app.db.database.async_session_maker") as mock_session:
            mock_session.return_value.__aenter__.return_value = session_instance
            yield

    @pytest.mark.asyncio
    async def test_calls_append_expense(self, registry, mock_store):
        await registry.run("register_expense", amount=850.0, description="farmacia")
        mock_store.append_expense.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_success_and_expense_id(self, registry):
        result = await registry.run("register_expense", amount=850.0, description="farmacia")
        assert result["success"] is True
        assert result["expense_id"] == 3

    @pytest.mark.asyncio
    async def test_uses_default_category(self, registry, mock_store):
        await registry.run("register_expense", amount=100.0, description="misc")
        expense_arg = mock_store.append_expense.call_args[0][1]
        assert expense_arg.category == "General"

    @pytest.mark.asyncio
    async def test_returns_failure_when_store_fails(self, registry, mock_store):
        mock_store.append_expense.return_value = None
        result = await registry.run("register_expense", amount=100.0, description="test")
        assert result["success"] is False


class TestSummaries:
    @pytest.mark.asyncio
    async def test_monthly_summary_returns_total_and_categories(self, registry):
        result = await registry.run("get_monthly_summary")
        assert result["total"] == 5000.0
        assert result["categories"] == {"Comida": 2000.0, "Transporte": 3000.0}
        assert result["monthly_commitment"] == 70000.0
        assert result["total_with_commitments"] == 75000.0
        assert result["category_details"] == [
            {
                "category": "Transporte",
                "emoji": "🚗",
                "total": 3000.0,
                "movement_count": 2,
                "observation": "2 mov. • frecuente: Uber (2)",
            },
            {
                "category": "Comida",
                "emoji": "🍔",
                "total": 2000.0,
                "movement_count": 2,
                "observation": "2 mov. • frecuente: Burger Club (2)",
            },
        ]
        assert "RESUMEN" in result["formatted_summary"]
        assert "POR CATEGORÍA" in result["formatted_summary"]
        assert "🚗 Transporte *$3.000*" in result["formatted_summary"]
        assert "_Obs:_ 2 mov. • frecuente: Uber (2)" in result["formatted_summary"]
        assert "🍔 Comida *$2.000*" in result["formatted_summary"]

    @pytest.mark.asyncio
    @patch("app.agent.skills.local_now_for_phone")
    async def test_monthly_summary_uses_current_month(self, mock_local_now, registry, mock_store):
        from datetime import datetime

        mock_local_now.return_value = datetime(2026, 3, 20)
        await registry.run("get_monthly_summary")
        mock_store.get_monthly_total.assert_called_once_with("5491123456789", 3, 2026)

    @pytest.mark.asyncio
    async def test_category_breakdown_can_filter(self, registry):
        result = await registry.run("get_category_breakdown", category="Comida")
        assert result["category"] == "Comida"
        assert result["breakdown"] == {"Comida": 2000.0}
        assert result["entries"] == [
            {
                "expense_id": 10,
                "fecha": "2026-02-18",
                "hora": "09:30",
                "monto": 1200.0,
                "moneda": "ARS",
                "shop": "Burger Club",
                "descripcion": "combo burger",
            },
            {
                "expense_id": 13,
                "fecha": "2026-02-21",
                "hora": "13:15",
                "monto": 800.0,
                "moneda": "ARS",
                "shop": "Burger Club",
                "descripcion": "almuerzo",
            },
        ]
        assert "Burger Club" in result["formatted_breakdown"]
        assert "2026-02-18" in result["formatted_breakdown"]

    @pytest.mark.asyncio
    async def test_recent_expenses_uses_limit(self, registry, mock_store):
        result = await registry.run("get_recent_expenses", limit=10)
        assert result["count"] == 2
        mock_store.get_recent_expenses.assert_called_once_with("5491123456789", n=10)


class TestDeleteAndSearch:
    @pytest.mark.asyncio
    async def test_delete_last_expense_calls_store(self, registry, mock_store):
        result = await registry.run("delete_last_expense")
        mock_store.delete_last_expense.assert_called_once_with("5491123456789")
        assert result["success"] is True
        assert result["deleted"]["expense_id"] == 11

    @pytest.mark.asyncio
    async def test_delete_last_expense_returns_error_when_empty(self, registry, mock_store):
        mock_store.delete_last_expense.return_value = None
        result = await registry.run("delete_last_expense")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_search_expenses_passes_filters(self, registry, mock_store):
        result = await registry.run(
            "search_expenses",
            query="uber",
            date_from="2026-02-01",
            date_to="2026-02-29",
        )
        assert result["count"] == 4
        mock_store.search_expenses.assert_called_once_with(
            "5491123456789",
            query="uber",
            date_from="2026-02-01",
            date_to="2026-02-29",
        )


class TestBudgets:
    @pytest.mark.asyncio
    async def test_save_budget_calls_budget_service(self, registry):
        result = await registry.run("save_budget", category="Comida", limit_amount=200000)
        assert result["success"] is True
        registry.budget_service.save_budget.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_list_budgets_returns_payload(self, registry):
        result = await registry.run("list_budgets")
        assert result["count"] == 1
        assert result["budgets"][0]["category"] == "Comida"


class TestInsights:
    @pytest.mark.asyncio
    async def test_get_spending_comparison_calls_insights_service(self, registry):
        result = await registry.run("get_spending_comparison", period="weekly", group_by="merchant")
        assert result["status"] == "ok"
        registry.insights_service.compare_spending_periods.assert_awaited_once_with(
            "5491123456789",
            period="weekly",
            group_by="merchant",
        )

    @pytest.mark.asyncio
    async def test_get_spending_insights_calls_insights_service(self, registry):
        result = await registry.run("get_spending_insights")
        assert result["status"] == "ok"
        registry.insights_service.detect_spending_leaks.assert_awaited_once_with("5491123456789")


class TestProjections:
    @pytest.mark.asyncio
    async def test_project_savings_calls_projection_service(self, registry):
        result = await registry.run(
            "project_savings",
            category="Comida",
            reduction_percent=20,
            frequency="monthly",
            horizon_months=6,
        )
        assert result["status"] == "ok"
        registry.projection_service.project_savings.assert_awaited_once_with(
            "5491123456789",
            amount=None,
            frequency="monthly",
            horizon_months=6,
            category="Comida",
            reduction_percent=20,
        )


class TestLiabilities:
    @pytest.mark.asyncio
    async def test_create_liability_calls_service(self, registry):
        result = await registry.run(
            "create_liability",
            kind="installment",
            description="Notebook",
            monthly_amount=50000,
            remaining_periods=6,
        )
        assert result["success"] is True
        registry.liability_service.create_liability.assert_awaited_once_with(
            "5491123456789",
            kind="installment",
            description="Notebook",
            monthly_amount=50000.0,
            remaining_periods=6,
            currency="ARS",
        )

    @pytest.mark.asyncio
    async def test_get_monthly_commitment_calls_service(self, registry):
        result = await registry.run("get_monthly_commitment")
        assert result["success"] is True
        registry.liability_service.get_monthly_commitment.assert_awaited_once_with(
            "5491123456789"
        )

    @pytest.mark.asyncio
    async def test_close_liability_calls_service(self, registry):
        result = await registry.run("close_liability", liability_id=8)
        assert result["success"] is True
        registry.liability_service.close_liability.assert_awaited_once_with(
            "5491123456789",
            liability_id=8,
        )


class TestEducation:
    @pytest.mark.asyncio
    async def test_get_financial_education_calls_service(self, registry):
        result = await registry.run("get_financial_education")
        assert result["status"] == "ok"
        registry.education_service.evaluate_financial_education.assert_awaited_once_with(
            "5491123456789"
        )


class TestReports:
    @pytest.mark.asyncio
    async def test_generate_expense_report_blocks_free_when_quota_exhausted(self, registry):
        with patch(
            "app.agent.skills.ReportSkill._get_plan_context",
            new=AsyncMock(return_value=(1, "FREE", "UTC")),
        ):
            with patch(
                "app.services.plan_usage.check_quota",
                new=AsyncMock(
                    return_value=QuotaDecision(
                        allowed=False,
                        limit=3,
                        used=3,
                        remaining=0,
                        quota_key="expense_report_pdf",
                        period_kind="monthly",
                    )
                ),
            ):
                result = await registry.run("generate_expense_report")

        assert result["success"] is False
        assert result["error"] == "report_quota_exceeded"
        assert "3 reportes por mes" in result["formatted_confirmation"]

    @pytest.mark.asyncio
    async def test_generate_expense_report_keeps_premium_unlimited(self, registry):
        with patch(
            "app.agent.skills.ReportSkill._get_plan_context",
            new=AsyncMock(return_value=(1, "PREMIUM", "UTC")),
        ):
            with patch("app.services.report_pdf.generate_expense_report", return_value=b"%PDF-1.4"):
                with patch("app.services.whatsapp.upload_media", new=AsyncMock(return_value="media-id")) as mock_upload:
                    with patch("app.services.whatsapp.send_document", new=AsyncMock(return_value="wamid-1")) as mock_send:
                        result = await registry.run("generate_expense_report", month=2, year=2026)

        assert result["success"] is True
        assert result["filename"] == "Reporte_Gastos_Febrero_2026.pdf"
        mock_upload.assert_awaited_once()
        mock_send.assert_awaited_once()
