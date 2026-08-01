"""
MV Cliente IA · exportación
============================
La lista sirve cuando entra al CRM o al secuenciador de correos, así que la
corrida sale en CSV (universal) y en XLSX cuando hay openpyxl.

Formato de números: el estándar del proyecto —score con un decimal, sin
notación científica— y una fila por decisor, que es la unidad con la que
trabaja quien manda los correos.
"""
from __future__ import annotations

import csv
import io
from pathlib import Path

from . import rutas
from .modelos import Corrida

COLUMNAS = [
    "prioridad", "nivel", "pais", "score", "empresa", "dominio", "sector",
    "ciudad", "empleados", "decisor", "cargo", "seniority", "email", "idioma",
    "asunto", "cuerpo", "seguimiento", "senales", "campana", "sintetico",
]


def filas(corrida: Corrida) -> list[dict]:
    """Una fila por decisor, con su correo si la fase 6 lo escribió."""
    prospectos = {p.id: p for p in corrida.prospectos}
    emails = {e.decisor_id: e for e in corrida.emails}
    campanas = {c.id: c for c in corrida.campanas}
    salida: list[dict] = []
    for d in corrida.decisores:
        p = prospectos.get(d.prospecto_id)
        if not p:
            continue
        e = emails.get(d.id)
        c = campanas.get(p.campana_id)
        salida.append({
            "prioridad": p.prioridad,
            "nivel": p.nivel,
            "pais": p.pais,
            "score": round(d.score, 1),
            "empresa": p.nombre,
            "dominio": p.dominio,
            "sector": p.sector,
            "ciudad": p.ciudad,
            "empleados": p.empleados,
            "decisor": d.nombre,
            "cargo": d.cargo,
            "seniority": d.seniority,
            "email": d.email,
            "idioma": d.idioma,
            "asunto": e.asunto if e else "",
            "cuerpo": e.cuerpo if e else "",
            "seguimiento": e.seguimiento if e else "",
            "senales": " | ".join(p.senales),
            "campana": c.nombre if c else p.campana_id,
            "sintetico": "sí" if (d.sintetico or p.sintetico) else "no",
        })
    return salida


def a_csv(corrida: Corrida) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNAS, lineterminator="\n")
    w.writeheader()
    w.writerows(filas(corrida))
    return buf.getvalue()


def guardar_csv(corrida: Corrida, destino: Path | None = None) -> Path:
    destino = destino or (rutas.dir_exports() / f"{corrida.dominio}_{corrida.id}.csv")
    destino.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig: sin el BOM, Excel en Windows abre los acentos rotos.
    destino.write_text(a_csv(corrida), encoding="utf-8-sig")
    return destino


def guardar_xlsx(corrida: Corrida, destino: Path | None = None) -> Path:
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
    except ImportError as e:                                # pragma: no cover
        raise RuntimeError("Falta openpyxl (pip install openpyxl)") from e

    destino = destino or (rutas.dir_exports() / f"{corrida.dominio}_{corrida.id}.xlsx")
    destino.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    ws = wb.active
    ws.title = "Prospectos"
    encabezado = Font(bold=True, color="FFFFFF")
    fondo = PatternFill("solid", start_color="0E1628")      # navy de la marca
    ws.append([c.upper() for c in COLUMNAS])
    for celda in ws[1]:
        celda.font = encabezado
        celda.fill = fondo
        celda.alignment = Alignment(horizontal="left")
    for fila in filas(corrida):
        ws.append([fila[c] for c in COLUMNAS])
    anchos = {"empresa": 34, "sector": 30, "decisor": 24, "cargo": 28, "email": 34,
              "asunto": 46, "cuerpo": 70, "seguimiento": 60, "senales": 60, "campana": 34}
    for i, col in enumerate(COLUMNAS, start=1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = anchos.get(col, 12)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    resumen = wb.create_sheet("Resumen")
    r = corrida.resumen()
    resumen.append(["Dominio", corrida.dominio])
    resumen.append(["Corrida", corrida.id])
    resumen.append(["Modo", corrida.modo])
    resumen.append(["Estado", corrida.estado])
    resumen.append([])
    resumen.append(["Prospectos por ola", ""])
    for nivel, valor in r["prospectos_por_nivel"].items():
        resumen.append([nivel, valor])
    resumen.append([])
    resumen.append(["Correos por idioma", ""])
    for idioma, valor in r["emails_por_idioma"].items():
        resumen.append([idioma, valor])
    resumen.column_dimensions["A"].width = 24
    resumen.column_dimensions["B"].width = 40

    wb.save(destino)
    return destino
