"""Tests para el servicio de generación de reportes PDF."""
from __future__ import annotations

import pytest

from app.services.report_pdf import generate_expense_report, _render_pie_chart, _render_bar_chart

SAMPLE_CATEGORIES = {
    "Comida": 45000.0,
    "Transporte": 18000.0,
    "Hogar": 12000.0,
    "Otros": 5000.0,
}

SAMPLE_EXPENSES = [
    {"fecha": "2026-03-01", "hora": "12:00", "monto": 15000, "moneda": "ARS", "descripcion": "Rappi", "categoria": "Comida", "shop": "Rappi"},
    {"fecha": "2026-03-05", "hora": "09:30", "monto": 8000,  "moneda": "ARS", "descripcion": "Uber",  "categoria": "Transporte", "shop": None},
    {"fecha": "2026-03-10", "hora": "20:00", "monto": 12000, "moneda": "ARS", "descripcion": "Supermercado", "categoria": "Hogar", "shop": "Dia"},
    {"fecha": "2026-03-15", "hora": "15:00", "monto": 30000, "moneda": "ARS", "descripcion": "Sushi", "categoria": "Comida", "shop": "Palermo Sushi"},
    {"fecha": "2026-03-20", "hora": "11:00", "monto": 10000, "moneda": "ARS", "descripcion": "Taxi", "categoria": "Transporte", "shop": None},
    {"fecha": "2026-03-28", "hora": "18:00", "monto": 5000,  "moneda": "ARS", "descripcion": "Varios", "categoria": "Otros", "shop": None},
]


def test_generate_expense_report_returns_pdf_bytes():
    result = generate_expense_report(
        month=3, year=2026, total=80000.0, currency="ARS",
        categories=SAMPLE_CATEGORIES, expenses=SAMPLE_EXPENSES,
    )
    assert isinstance(result, bytes)
    assert result[:4] == b"%PDF", "El resultado debe ser un PDF válido"


def test_generate_expense_report_empty_expenses():
    """Con lista vacía sigue generando un PDF (sin filas en la tabla)."""
    result = generate_expense_report(
        month=3, year=2026, total=0.0, currency="ARS",
        categories={}, expenses=[],
    )
    assert isinstance(result, bytes)
    assert result[:4] == b"%PDF"


def test_generate_expense_report_single_category():
    result = generate_expense_report(
        month=1, year=2026, total=50000.0, currency="ARS",
        categories={"Comida": 50000.0},
        expenses=[SAMPLE_EXPENSES[0]],
    )
    assert result[:4] == b"%PDF"


def test_render_pie_chart_returns_png():
    png = _render_pie_chart(SAMPLE_CATEGORIES, "ARS")
    assert isinstance(png, bytes)
    assert png[:8] == b"\x89PNG\r\n\x1a\n", "Debe ser un PNG válido"


def test_render_pie_chart_empty_categories():
    """Categorías vacías no debe crashear."""
    png = _render_pie_chart({}, "ARS")
    assert isinstance(png, bytes)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_bar_chart_returns_png():
    png = _render_bar_chart(SAMPLE_EXPENSES, month=3, year=2026, currency="ARS")
    assert isinstance(png, bytes)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_bar_chart_empty_expenses():
    """Sin gastos debe generar barras en cero, no crashear."""
    png = _render_bar_chart([], month=3, year=2026, currency="ARS")
    assert isinstance(png, bytes)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_generate_expense_report_large_table():
    """Tabla con muchos gastos debe paginar correctamente."""
    many_expenses = [
        {
            "fecha": f"2026-03-{(i % 28) + 1:02d}",
            "hora": "10:00",
            "monto": 1000 * (i + 1),
            "moneda": "ARS",
            "descripcion": f"Gasto {i}",
            "categoria": "Otros",
            "shop": None,
        }
        for i in range(80)
    ]
    result = generate_expense_report(
        month=3, year=2026, total=sum(e["monto"] for e in many_expenses),
        currency="ARS", categories={"Otros": 1000.0}, expenses=many_expenses,
    )
    assert result[:4] == b"%PDF"
