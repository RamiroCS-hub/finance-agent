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
    "Monto Original",
    "Moneda Original",
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

    def append_expense(self, phone: str, expense: ParsedExpense) -> int:
        """
        Agrega un gasto a la hoja del usuario.
        Retorna el índice de fila del gasto nuevo (1-based), o 0 si hubo un error.
        """
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
                expense.original_amount or "",
                expense.original_currency or "",
            ]
            # Contar filas actuales para saber el índice de la nueva
            current_rows = ws.get_all_values()
            row_index = len(current_rows) + 1
            ws.append_row(row, value_input_option="USER_ENTERED")
            logger.info(
                "Gasto registrado para %s: %s %s (fila %d)",
                phone, expense.amount, expense.currency, row_index,
            )
            return row_index
        except Exception as e:
            logger.error("Error guardando gasto para %s: %s", phone, e)
            return 0

    def delete_expense(self, phone: str, row_index: int) -> bool:
        """
        Elimina una fila de gasto por índice (1-based).
        Retorna True si tuvo éxito, False si hubo un error.
        """
        try:
            ws = self._get_or_create_user_sheet(phone)
            ws.delete_rows(row_index)
            logger.info("Gasto eliminado para %s en fila %d", phone, row_index)
            return True
        except Exception as e:
            logger.error("Error eliminando gasto para %s: %s", phone, e)
            return False

    def search_expenses(
        self,
        phone: str,
        query: "str | None" = None,
        date_from: "str | None" = None,
        date_to: "str | None" = None,
    ) -> list[dict]:
        """
        Busca gastos filtrando por texto en descripción y/o rango de fechas.

        - query: texto a buscar en la columna Descripción (case-insensitive).
        - date_from / date_to: límites en formato YYYY-MM-DD (inclusivos).
        - Retorna lista de dicts con row_index incluido para facilitar delete_expense.
        """
        try:
            ws = self.spreadsheet.worksheet(self._get_user_sheet_name(phone))
            all_rows = ws.get_all_values()
        except gspread.WorksheetNotFound:
            return []

        data_rows = all_rows[1:]  # omitir fila de headers (fila 1)
        result = []

        for i, row in enumerate(data_rows):
            row_index = i + 2  # +1 de 0-based→1-based, +1 por la fila de headers
            try:
                fecha = row[0] if len(row) > 0 else ""
                descripcion = row[4].lower() if len(row) > 4 else ""

                if query and query.lower() not in descripcion:
                    continue
                if date_from and fecha < date_from:
                    continue
                if date_to and fecha > date_to:
                    continue

                result.append(
                    {
                        "row_index": row_index,
                        "fecha": row[0] if len(row) > 0 else "",
                        "hora": row[1] if len(row) > 1 else "",
                        "monto": float(row[2]) if len(row) > 2 and row[2] else 0.0,
                        "moneda": row[3] if len(row) > 3 else "",
                        "descripcion": row[4] if len(row) > 4 else "",
                        "categoria": row[5] if len(row) > 5 else "",
                    }
                )
            except (ValueError, IndexError):
                continue

        return result

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

    def list_user_phones(self) -> list[str]:
        users_ws = self.spreadsheet.worksheet("Usuarios")
        phones = users_ws.col_values(1)
        return [phone for phone in phones[1:] if phone]

    def export_expenses(self, phone: str) -> list[dict]:
        rows = self._get_all_expenses(phone)
        exported: list[dict] = []
        for row in rows:
            exported.append(
                {
                    "fecha": row[0] if len(row) > 0 else "",
                    "hora": row[1] if len(row) > 1 else "",
                    "monto": row[2] if len(row) > 2 else "",
                    "moneda": row[3] if len(row) > 3 else "",
                    "descripcion": row[4] if len(row) > 4 else "",
                    "categoria": row[5] if len(row) > 5 else "",
                    "shop": "",
                    "calculo": row[6] if len(row) > 6 else "",
                    "mensaje_original": row[7] if len(row) > 7 else "",
                    "monto_original": row[8] if len(row) > 8 else "",
                    "moneda_original": row[9] if len(row) > 9 else "",
                }
            )
        return exported

    def _get_all_expenses(self, phone: str) -> list[list[str]]:
        """Retorna todas las filas de gastos del usuario (sin headers)."""
        try:
            ws = self.spreadsheet.worksheet(self._get_user_sheet_name(phone))
            rows = ws.get_all_values()
            return rows[1:]  # skip headers
        except gspread.WorksheetNotFound:
            return []
