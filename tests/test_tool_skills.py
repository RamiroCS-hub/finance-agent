from unittest.mock import MagicMock

from app.agent.tools import ToolRegistry


def test_tool_registry_is_composed_from_domain_skills():
    registry = ToolRegistry(expense_store=MagicMock(), phone="+5491112345678")

    skill_names = [type(skill).__name__ for skill in registry.skills]

    assert skill_names == [
        "ExpenseSkill",
        "BudgetSkill",
        "InsightSkill",
        "LiabilitySkill",
        "GroupSkill",
        "ReportSkill",
        "UtilitySkill",
    ]


def test_skill_composition_keeps_expected_tool_names():
    registry = ToolRegistry(expense_store=MagicMock(), phone="+5491112345678")

    names = {tool.name for tool in registry.definitions()}

    assert "register_expense" in names
    assert "project_savings" in names
    assert "create_liability" in names
    assert "get_financial_education" in names
    assert "generate_expense_report" in names
