"""
Tests para app/agent/tools.py — Fase 4: ToolRegistry.

Verifica que cada herramienta llame a SheetsService con los argumentos correctos
y que retorne el formato esperado.
"""
from __future__ import annotations

from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from app.agent.tools import ToolRegistry
from app.models.agent import ToolDefinition


# ---------------------------------------------------------------------------
# Fixture: ToolRegistry con SheetsService mockeado
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_sheets():
    sheets = MagicMock()
    sheets.get_sheet_url.return_value = "https://docs.google.com/spreadsheets/d/abc123"
    sheets.get_monthly_total.return_value = 5000.0
    sheets.get_category_totals.return_value = {"Comida": 2000.0, "Transporte": 3000.0}
    sheets.get_recent_expenses.return_value = [
        {"fecha": "2026-02-19", "monto": 850.0, "descripcion": "uber", "categoria": "Transporte"},
        {"fecha": "2026-02-18", "monto": 500.0, "descripcion": "farmacia", "categoria": "Salud"},
    ]
    sheets.search_expenses.return_value = [
        {"row_index": 2, "fecha": "2026-02-18", "monto": 500.0, "descripcion": "farmacia", "categoria": "Salud"},
        {"row_index": 3, "fecha": "2026-02-19", "monto": 850.0, "descripcion": "uber", "categoria": "Transporte"},
    ]
    sheets.append_expense.return_value = 3
    sheets.delete_expense.return_value = True
    return sheets


@pytest.fixture
def registry(mock_sheets):
    return ToolRegistry(mock_sheets, "5491123456789")


# ---------------------------------------------------------------------------
# Definiciones
# ---------------------------------------------------------------------------


class TestDefinitions:
    def test_returns_ten_tools(self, registry):
        """ToolRegistry debe exponer exactamente 11 herramientas."""
        assert len(registry.definitions()) == 12

    def test_all_are_tool_definition_instances(self, registry):
        """Cada elemento debe ser un ToolDefinition."""
        assert all(isinstance(t, ToolDefinition) for t in registry.definitions())

    def test_expected_tool_names(self, registry):
        """Los nombres de las herramientas deben coincidir con el plan."""
        names = {t.name for t in registry.definitions()}
        expected = {
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
            "save_personality",
        }
        assert names == expected

    def test_all_tools_have_description(self, registry):
        """Todas las herramientas deben tener descripción no vacía."""
        assert all(t.description for t in registry.definitions())

    def test_all_tools_have_parameters_schema(self, registry):
        """Todas las herramientas deben tener parámetros JSON Schema válidos."""
        for tool in registry.definitions():
            assert "type" in tool.parameters
            assert tool.parameters["type"] == "object"


# ---------------------------------------------------------------------------
# run() — dispatch
# ---------------------------------------------------------------------------


class TestRun:
    def test_unknown_tool_raises_value_error(self, registry):
        """run() con nombre desconocido debe lanzar ValueError."""
        with pytest.raises(ValueError, match="desconocida"):
            registry.run("nonexistent_tool")

    def test_run_dispatches_to_correct_function(self, registry, mock_sheets):
        """run('get_sheet_url') debe ejecutar _get_sheet_url."""
        result = registry.run("get_sheet_url")
        assert "url" in result
        mock_sheets.get_sheet_url.assert_called_once()


# ---------------------------------------------------------------------------
# register_expense
# ---------------------------------------------------------------------------


class TestRegisterExpense:
    @pytest.fixture(autouse=True)
    def mock_db(self):
        with patch("app.db.database.async_session_maker") as mock_session:
            session_instance = AsyncMock()
            mock_session.return_value.__aenter__.return_value = session_instance
            yield mock_session
    @pytest.mark.asyncio
    async def test_calls_append_expense(self, registry, mock_sheets):
        """register_expense debe llamar a sheets.append_expense."""
        await registry.run("register_expense", amount=850.0, description="farmacia")
        mock_sheets.append_expense.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_success_true(self, registry):
        """Cuando append_expense retorna row_index > 0, success debe ser True."""
        result = await registry.run("register_expense", amount=850.0, description="farmacia")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_returns_row_index(self, registry):
        """El resultado debe incluir el row_index retornado por append_expense."""
        result = await registry.run("register_expense", amount=850.0, description="farmacia")
        assert result["row_index"] == 3

    @pytest.mark.asyncio
    async def test_uses_default_category_when_not_provided(self, registry, mock_sheets):
        """Si no se proporciona categoría, debe usar 'General'."""
        await registry.run("register_expense", amount=100.0, description="misc")
        expense_arg = mock_sheets.append_expense.call_args[0][1]
        assert expense_arg.category == "General"

    @pytest.mark.asyncio
    async def test_uses_provided_category(self, registry, mock_sheets):
        """Si se proporciona categoría, debe usarla."""
        await registry.run("register_expense", amount=500.0, description="uber", category="Transporte")
        expense_arg = mock_sheets.append_expense.call_args[0][1]
        assert expense_arg.category == "Transporte"

    @pytest.mark.asyncio
    async def test_returns_failure_when_append_returns_zero(self, registry, mock_sheets):
        """Si append_expense retorna 0 (error), success debe ser False."""
        mock_sheets.append_expense.return_value = 0
        result = await registry.run("register_expense", amount=100.0, description="test")
        assert result["success"] is False


# ---------------------------------------------------------------------------
# get_monthly_summary
# ---------------------------------------------------------------------------


class TestGetMonthlySummary:
    def test_returns_total(self, registry):
        """El resultado debe incluir 'total'."""
        result = registry.run("get_monthly_summary")
        assert "total" in result
        assert result["total"] == 5000.0

    def test_returns_categories(self, registry):
        """El resultado debe incluir 'categories' como dict."""
        result = registry.run("get_monthly_summary")
        assert "categories" in result
        assert isinstance(result["categories"], dict)

    @patch("app.agent.tools.datetime")
    def test_uses_current_month_when_not_specified(self, mock_datetime, registry, mock_sheets):
        """Sin argumentos, debe usar el mes y año actuales."""
        from datetime import datetime
        mock_now = datetime(2026, 3, 20)
        mock_datetime.now.return_value = mock_now
        
        registry.run("get_monthly_summary")
        mock_sheets.get_monthly_total.assert_called_once_with(
            "5491123456789", 3, 2026
        )

    def test_uses_provided_month_year(self, registry, mock_sheets):
        """Con mes y año explícitos, debe usarlos."""
        registry.run("get_monthly_summary", month=1, year=2025)
        mock_sheets.get_monthly_total.assert_called_once_with("5491123456789", 1, 2025)


# ---------------------------------------------------------------------------
# get_recent_expenses
# ---------------------------------------------------------------------------


class TestGetRecentExpenses:
    def test_returns_expenses_list(self, registry):
        """El resultado debe incluir 'expenses' como lista."""
        result = registry.run("get_recent_expenses")
        assert "expenses" in result
        assert isinstance(result["expenses"], list)

    def test_returns_count(self, registry):
        """El resultado debe incluir 'count'."""
        result = registry.run("get_recent_expenses")
        assert "count" in result
        assert result["count"] == 2

    def test_default_limit_is_five(self, registry, mock_sheets):
        """Sin argumentos, limit debe ser 5."""
        registry.run("get_recent_expenses")
        mock_sheets.get_recent_expenses.assert_called_once_with("5491123456789", n=5)

    def test_custom_limit(self, registry, mock_sheets):
        """Con limit explícito, debe usarlo."""
        registry.run("get_recent_expenses", limit=10)
        mock_sheets.get_recent_expenses.assert_called_once_with("5491123456789", n=10)


# ---------------------------------------------------------------------------
# delete_last_expense
# ---------------------------------------------------------------------------


class TestDeleteLastExpense:
    def test_calls_search_expenses(self, registry, mock_sheets):
        """delete_last_expense debe llamar a search_expenses para obtener row_index."""
        registry.run("delete_last_expense")
        mock_sheets.search_expenses.assert_called_once_with("5491123456789")

    def test_calls_delete_expense_with_last_row_index(self, registry, mock_sheets):
        """delete_last_expense debe llamar a delete_expense con el índice del último gasto."""
        registry.run("delete_last_expense")
        # search_expenses retorna [row_index=2, row_index=3]; el último es 3
        mock_sheets.delete_expense.assert_called_once_with("5491123456789", 3)

    def test_returns_success_true(self, registry):
        """Cuando delete_expense retorna True, success debe ser True."""
        result = registry.run("delete_last_expense")
        assert result["success"] is True

    def test_returns_deleted_expense_info(self, registry, mock_sheets):
        """El resultado debe incluir la info del gasto eliminado."""
        result = registry.run("delete_last_expense")
        assert "deleted" in result
        assert result["deleted"]["row_index"] == 3

    def test_returns_error_when_no_expenses(self, registry, mock_sheets):
        """Si no hay gastos, debe retornar success=False con mensaje de error."""
        mock_sheets.search_expenses.return_value = []
        result = registry.run("delete_last_expense")
        assert result["success"] is False
        assert "error" in result

    def test_returns_error_when_delete_fails(self, registry, mock_sheets):
        """Si delete_expense falla, debe retornar success=False."""
        mock_sheets.delete_expense.return_value = False
        result = registry.run("delete_last_expense")
        assert result["success"] is False


# ---------------------------------------------------------------------------
# search_expenses
# ---------------------------------------------------------------------------


class TestSearchExpenses:
    def test_returns_expenses_and_count(self, registry):
        """El resultado debe incluir 'expenses' y 'count'."""
        result = registry.run("search_expenses", query="uber")
        assert "expenses" in result
        assert "count" in result

    def test_passes_query_to_sheets(self, registry, mock_sheets):
        """Los parámetros de búsqueda deben pasarse a sheets.search_expenses."""
        registry.run("search_expenses", query="uber", date_from="2026-02-01")
        mock_sheets.search_expenses.assert_called_once_with(
            "5491123456789", query="uber", date_from="2026-02-01", date_to=None
        )


# ---------------------------------------------------------------------------
# get_category_breakdown
# ---------------------------------------------------------------------------


class TestGetCategoryBreakdown:
    def test_returns_breakdown_dict(self, registry):
        """El resultado debe incluir 'breakdown' como dict."""
        result = registry.run("get_category_breakdown")
        assert "breakdown" in result
        assert isinstance(result["breakdown"], dict)

    @patch("app.agent.tools.datetime")
    def test_uses_current_month_when_not_specified(self, mock_datetime, registry, mock_sheets):
        """Sin argumentos, debe usar el mes y año actuales."""
        from datetime import datetime
        mock_now = datetime(2026, 3, 20)
        mock_datetime.now.return_value = mock_now

        registry.run("get_category_breakdown")
        mock_sheets.get_category_totals.assert_called_once_with(
            "5491123456789", 3, 2026
        )

    def test_filters_by_specific_category(self, registry, mock_sheets):
        """Con category explícita, devuelve solo esa categoría."""
        result = registry.run("get_category_breakdown", category="Comida")
        assert result["category"] == "Comida"
        assert "Transporte" not in result["breakdown"]
        assert "Comida" in result["breakdown"]

    def test_without_category_returns_all(self, registry):
        """Sin category, devuelve todas las categorías."""
        result = registry.run("get_category_breakdown")
        assert result["breakdown"] == {"Comida": 2000.0, "Transporte": 3000.0}


# ---------------------------------------------------------------------------
# get_sheet_url
# ---------------------------------------------------------------------------


class TestGetSheetUrl:
    def test_returns_url(self, registry):
        """El resultado debe incluir 'url'."""
        result = registry.run("get_sheet_url")
        assert "url" in result
        assert result["url"].startswith("https://")
