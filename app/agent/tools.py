from __future__ import annotations

import logging

from app.agent.skills import (
    BudgetSkill,
    ExpenseSkill,
    GroupSkill,
    InsightSkill,
    LiabilitySkill,
    ReportSkill,
    ToolExecutionContext,
    UtilitySkill,
)
from app.services.alerts import AlertService
from app.services.budgets import BudgetService
from app.services.education import EducationService
from app.services.expenses import ExpenseService
from app.services.group_expenses import GroupExpenseService
from app.services.insights import SpendingInsightsService
from app.services.liabilities import LiabilityService
from app.services.projections import SavingsProjectionService
from app.services.timezones import local_now_for_phone  # compat for patched tests

logger = logging.getLogger(__name__)


def _infer_channel(phone: str, channel: str | None = None) -> str:
    if channel:
        return channel
    if phone.startswith("telegram:"):
        return "telegram"
    return "whatsapp"


class ToolRegistry:
    """
    Registro de herramientas compuesto por skills de dominio.
    Mantiene el mismo contrato observable hacia el agente/LLM.
    """

    def __init__(
        self,
        expense_store: ExpenseService | None = None,
        phone: str = "",
        channel: str | None = None,
        chat_type: str = "private",
        group_id: str | None = None,
        sheets: ExpenseService | None = None,
    ) -> None:
        self.expense_store = expense_store or sheets
        self.phone = phone
        self.channel = _infer_channel(phone, channel)
        self.chat_type = chat_type
        self.group_id = group_id

        # Servicios compartidos, expuestos como atributos para compatibilidad con tests y callers.
        self.group_expense_service = GroupExpenseService()
        self.liability_service = LiabilityService()
        self.budget_service = BudgetService()
        self.alert_service = AlertService()
        self.insights_service = SpendingInsightsService()
        self.projection_service = SavingsProjectionService()
        self.education_service = EducationService()

        self.context = ToolExecutionContext(
            expense_store=self.expense_store,
            phone=self.phone,
            channel=self.channel,
            chat_type=self.chat_type,
            group_id=self.group_id,
            group_expense_service=self.group_expense_service,
            liability_service=self.liability_service,
            budget_service=self.budget_service,
            alert_service=self.alert_service,
            insights_service=self.insights_service,
            projection_service=self.projection_service,
            education_service=self.education_service,
        )
        self.skills = [
            ExpenseSkill(self.context),
            BudgetSkill(self.context),
            InsightSkill(self.context),
            LiabilitySkill(self.context),
            GroupSkill(self.context),
            ReportSkill(self.context),
            UtilitySkill(self.context),
        ]
        self._tools = {
            tool.name: tool
            for skill in self.skills
            for tool in skill.definitions()
        }

    def definitions(self) -> list:
        return list(self._tools.values())

    def run(self, name: str, **kwargs):
        if name not in self._tools:
            raise ValueError(f"Herramienta desconocida: '{name}'")
        tool = self._tools[name]
        logger.debug("Ejecutando herramienta '%s' con args: %s", name, kwargs)
        return tool.fn(**kwargs)
