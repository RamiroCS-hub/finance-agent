from __future__ import annotations

import logging
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

from app.config import settings
from app.models.expense import ParsedExpense

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

EXPENSE_HEADERS = [
    "Fecha",
    "Hora",
    "Monto",
    "Moneda",
    "Descripción",
    "Categoría",
    "Cálculo",
    "Mensaje Original",
]

USERS_HEADERS = ["Teléfono", "Nombre", "Moneda Default", "Fecha Registro"]


class SheetsService:
    def __init__(self) -> None:
        creds = Credentials.from_service_account_file(
            settings.GOOGLE_SHEETS_CREDENTIALS_PATH, scopes=SCOPES
        )
        self.gc = gspread.authorize(creds)
        self.spreadsheet = self.gc.open_by_key(settings.GOOGLE_SPREADSHEET_ID)
        self._ensure_users_sheet()

    def _ensure_users_sheet(self) -> None:
        """Crea la hoja Usuarios si no existe."""
        try:
            self.spreadsheet.worksheet("Usuarios")
        except gspread.WorksheetNotFound:
            ws = self.spreadsheet.add_worksheet("Usuarios", rows=1, cols=len(USERS_HEADERS))
            ws.append_row(USERS_HEADERS)
            logger.info("Hoja 'Usuarios' creada")

    def _get_user_sheet_name(self, phone: str) -> str:
        return f"Gastos_{phone}"

    def _get_or_create_user_sheet(self, phone: str) -> gspread.Worksheet:
        """Obtiene la hoja de gastos del usuario, la crea si no existe."""
        sheet_name = self._get_user_sheet_name(phone)
        try:
            return self.spreadsheet.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            ws = self.spreadsheet.add_worksheet(sheet_name, rows=1, cols=len(EXPENSE_HEADERS))
            ws.append_row(EXPENSE_HEADERS)
            logger.info("Hoja '%s' creada para usuario %s", sheet_name, phone)
            return ws

    def ensure_user(self, phone: str) -> bool:
        """
        Registra un usuario nuevo si no existe.
        Retorna True si el usuario es nuevo, False si ya existía.
        """
        users_ws = self.spreadsheet.worksheet("Usuarios")
        phones = users_ws.col_values(1)  # Columna A = Teléfono

        if phone in phones:
            return False

        # Usuario nuevo: registrar y crear su hoja de gastos
        now = datetime.now()
        users_ws.append_row([phone, "", settings.DEFAULT_CURRENCY, now.strftime("%Y-%m-%d")])
        self._get_or_create_user_sheet(phone)
        logger.info("Usuario nuevo registrado: %s", phone)
        return True

    def append_expense(self, phone: str, expense: ParsedExpense) -> bool:
        """Agrega un gasto a la hoja del usuario."""
        try:
            ws = self._get_or_create_user_sheet(phone)
            now = datetime.now()
            row = [
                now.strftime("%Y-%m-%d"),
                now.strftime("%H:%M"),
                expense.amount,
                expense.currency,
                expense.description,
                expense.category,
                expense.calculation or "",
                expense.raw_message,
            ]
            ws.append_row(row, value_input_option="USER_ENTERED")
            logger.info("Gasto registrado para %s: %s %s", phone, expense.amount, expense.currency)
            return True
        except Exception as e:
            logger.error("Error guardando gasto para %s: %s", phone, e)
            return False

    def get_monthly_total(self, phone: str, month: int, year: int) -> float:
        """Obtiene el total de gastos del mes (solo moneda default)."""
        expenses = self._get_all_expenses(phone)
        total = 0.0
        for row in expenses:
            try:
                date = datetime.strptime(row[0], "%Y-%m-%d")
                if date.month == month and date.year == year:
                    total += float(row[2])
            except (ValueError, IndexError):
                continue
        return total

    def get_category_totals(
        self, phone: str, month: int, year: int
    ) -> dict[str, float]:
        """Obtiene el desglose por categoría del mes."""
        expenses = self._get_all_expenses(phone)
        totals: dict[str, float] = {}
        for row in expenses:
            try:
                date = datetime.strptime(row[0], "%Y-%m-%d")
                if date.month == month and date.year == year:
                    category = row[5]
                    totals[category] = totals.get(category, 0) + float(row[2])
            except (ValueError, IndexError):
                continue
        return totals

    def get_recent_expenses(self, phone: str, n: int = 10) -> list[dict]:
        """Retorna los últimos N gastos del usuario."""
        expenses = self._get_all_expenses(phone)
        recent = expenses[-n:] if len(expenses) > n else expenses
        recent.reverse()
        result = []
        for row in recent:
            try:
                result.append(
                    {
                        "fecha": row[0],
                        "hora": row[1],
                        "monto": float(row[2]),
                        "moneda": row[3],
                        "descripcion": row[4],
                        "categoria": row[5],
                    }
                )
            except (ValueError, IndexError):
                continue
        return result

    def get_sheet_url(self) -> str:
        return f"https://docs.google.com/spreadsheets/d/{settings.GOOGLE_SPREADSHEET_ID}"

    def _get_all_expenses(self, phone: str) -> list[list[str]]:
        """Retorna todas las filas de gastos del usuario (sin headers)."""
        try:
            ws = self.spreadsheet.worksheet(self._get_user_sheet_name(phone))
            rows = ws.get_all_values()
            return rows[1:]  # skip headers
        except gspread.WorksheetNotFound:
            return []
