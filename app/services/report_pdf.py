"""
Genera reportes de gastos en formato PDF con gráficos de torta y barras.
Módulo puro: recibe datos estructurados, devuelve bytes. Sin DB ni WhatsApp.
"""
from __future__ import annotations

import calendar
import io
from typing import Any

import matplotlib
matplotlib.use("Agg")  # backend headless — seguro en servidores async
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from fpdf import FPDF

_CATEGORY_COLORS: dict[str, str] = {
    "Comida":          "#FF6B6B",
    "Transporte":      "#4ECDC4",
    "Salud":           "#45B7D1",
    "Supermercado":    "#96CEB4",
    "Entretenimiento": "#FFEAA7",
    "Ropa":            "#DDA0DD",
    "Educación":       "#98D8C8",
    "Educacion":       "#98D8C8",
    "Hogar":           "#F7DC6F",
    "Otros":           "#BDC3C7",
    "General":         "#BDC3C7",
}

_DEFAULT_COLOR = "#AEB6BF"

_MONTH_NAMES_ES = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


def generate_expense_report(
    month: int,
    year: int,
    total: float,
    currency: str,
    categories: dict[str, float],
    expenses: list[dict[str, Any]],
) -> bytes:
    """
    Genera un reporte PDF completo y retorna los bytes del archivo.

    Args:
        month:      Mes (1-12)
        year:       Año
        total:      Total gastado en el mes
        currency:   Código de moneda (e.g. "ARS")
        categories: {categoria: monto_total}
        expenses:   Lista de gastos serializados con campos:
                    fecha, hora, monto, moneda, descripcion, categoria, shop
    """
    pie_png = _render_pie_chart(categories, currency)
    bar_png = _render_bar_chart(expenses, month, year, currency)
    return _build_pdf(month, year, total, currency, pie_png, bar_png, expenses)


def _render_pie_chart(categories: dict[str, float], currency: str) -> bytes:
    """Gráfico de torta por categoría. Retorna PNG como bytes."""
    if not categories:
        categories = {"Sin gastos": 1.0}

    labels = list(categories.keys())
    sizes = list(categories.values())
    colors = [_CATEGORY_COLORS.get(lbl, _DEFAULT_COLOR) for lbl in labels]

    fig, ax = plt.subplots(figsize=(6, 5), dpi=120)
    wedges, texts, autotexts = ax.pie(
        sizes,
        labels=labels,
        colors=colors,
        autopct="%1.1f%%",
        startangle=140,
        pctdistance=0.8,
    )
    for t in texts:
        t.set_fontsize(9)
    for at in autotexts:
        at.set_fontsize(8)
        at.set_color("white")
        at.set_fontweight("bold")

    ax.set_title("Gastos por categoría", fontsize=12, fontweight="bold", pad=12)
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _render_bar_chart(
    expenses: list[dict[str, Any]],
    month: int,
    year: int,
    currency: str,
) -> bytes:
    """Gráfico de barras: gasto total por día del mes. Retorna PNG como bytes."""
    days_in_month = calendar.monthrange(year, month)[1]
    daily: dict[int, float] = {d: 0.0 for d in range(1, days_in_month + 1)}

    for exp in expenses:
        try:
            day = int(str(exp.get("fecha", "")).split("-")[-1])
            if 1 <= day <= days_in_month:
                daily[day] += float(exp.get("monto", 0))
        except (ValueError, IndexError):
            continue

    days = list(daily.keys())
    amounts = list(daily.values())

    fig, ax = plt.subplots(figsize=(8, 3.5), dpi=120)
    bar_colors = ["#4ECDC4" if a > 0 else "#EAECEE" for a in amounts]
    ax.bar(days, amounts, color=bar_colors, edgecolor="none", width=0.8)

    ax.set_xlabel("Día del mes", fontsize=9)
    ax.set_ylabel(f"Monto ({currency})", fontsize=9)
    ax.set_title(
        f"Gasto diario — {_MONTH_NAMES_ES[month]} {year}",
        fontsize=11,
        fontweight="bold",
    )
    ax.yaxis.set_major_formatter(
        mticker.FuncFormatter(lambda x, _: f"${x:,.0f}".replace(",", "."))
    )
    ax.set_xticks(days[::2])  # mostrar cada 2 días para no saturar el eje
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _build_pdf(
    month: int,
    year: int,
    total: float,
    currency: str,
    pie_png: bytes,
    bar_png: bytes,
    expenses: list[dict[str, Any]],
) -> bytes:
    """Ensambla el PDF completo con fpdf2. Retorna bytes del PDF."""
    month_name = _MONTH_NAMES_ES[month]
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(15, 15, 15)

    # ── Página 1: resumen + gráficos ─────────────────────────────────────────
    pdf.add_page()

    # Header
    pdf.set_fill_color(41, 128, 185)
    pdf.rect(0, 0, 210, 22, style="F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_xy(0, 5)
    pdf.cell(210, 12, f"Reporte de Gastos  -  {month_name} {year}", align="C")

    # Total
    pdf.set_text_color(30, 30, 30)
    pdf.set_xy(15, 28)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, f"Total gastado:", ln=0)
    pdf.set_font("Helvetica", "B", 13)
    total_fmt = f"${total:,.0f} {currency}".replace(",", ".")
    pdf.set_text_color(41, 128, 185)
    pdf.cell(0, 8, f"  {total_fmt}", ln=1)
    pdf.set_text_color(30, 30, 30)

    pdf.ln(2)

    # Gráfico de torta (izquierda)
    pie_buf = io.BytesIO(pie_png)
    pdf.image(pie_buf, x=10, y=pdf.get_y(), w=90)

    # Gráfico de barras (derecha, mismo y)
    bar_y = pdf.get_y()
    bar_buf = io.BytesIO(bar_png)
    pdf.image(bar_buf, x=105, y=bar_y, w=95)

    # Avanzar por debajo de los gráficos (aprox 75mm)
    pdf.set_y(bar_y + 78)

    # ── Página(s) de tabla detallada ─────────────────────────────────────────
    pdf.add_page()
    _render_expense_table(pdf, expenses, currency)

    return bytes(pdf.output())


def _render_expense_table(
    pdf: FPDF,
    expenses: list[dict[str, Any]],
    currency: str,
) -> None:
    """Renderiza la tabla de gastos detallada (puede ocupar múltiples páginas)."""
    # Encabezado de tabla
    def _draw_header() -> None:
        pdf.set_fill_color(41, 128, 185)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(22, 7, "Fecha", border=0, fill=True)
        pdf.cell(22, 7, "Hora", border=0, fill=True)
        pdf.cell(62, 7, "Descripción", border=0, fill=True)
        pdf.cell(32, 7, "Categoría", border=0, fill=True)
        pdf.cell(28, 7, f"Monto ({currency})", border=0, fill=True, align="R")
        pdf.cell(0, 7, "Comercio", border=0, fill=True, ln=1)
        pdf.set_text_color(30, 30, 30)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Detalle de gastos", ln=1)
    pdf.ln(1)
    _draw_header()

    pdf.set_font("Helvetica", "", 8)
    row_num = 0
    for exp in expenses:
        # Color alternado de filas
        if row_num % 2 == 0:
            pdf.set_fill_color(245, 248, 250)
        else:
            pdf.set_fill_color(255, 255, 255)

        fecha = str(exp.get("fecha", ""))
        hora = str(exp.get("hora", ""))
        desc = str(exp.get("descripcion", ""))[:35]
        cat = str(exp.get("categoria", exp.get("category", "")))[:18]
        monto = float(exp.get("monto", 0))
        monto_fmt = f"${monto:,.0f}".replace(",", ".")
        shop = str(exp.get("shop") or "")[:20]

        pdf.cell(22, 6, fecha, fill=True)
        pdf.cell(22, 6, hora, fill=True)
        pdf.cell(62, 6, desc, fill=True)
        pdf.cell(32, 6, cat, fill=True)
        pdf.cell(28, 6, monto_fmt, fill=True, align="R")
        pdf.cell(0, 6, shop, fill=True, ln=1)
        row_num += 1

        # Si llegamos al borde de la página, volver a dibujar el encabezado
        if pdf.get_y() > 270:
            pdf.add_page()
            _draw_header()
            pdf.set_font("Helvetica", "", 8)
