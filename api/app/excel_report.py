"""Exportación a Excel (`/api/reports/excel`).

Un libro con una hoja de portada (datos del estudio y contenido) y una hoja
por análisis con sus tablas numeradas, la interpretación y, donde aplica, un
gráfico nativo de Excel. No calcula nada: solo presenta las respuestas que la
API ya devolvió y que el frontend guardó en `analyses.result`.
"""

from __future__ import annotations

import io
import re
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference, ScatterChart, Series
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

MODULE_NAMES = {
    "data": "Datos",
    "variables": "Gráficos por variables",
    "attributes": "Gráficos por atributos",
    "assumptions": "Supuestos",
    "capability": "Capacidad",
    "design": "Diseño (ARL)",
    "sampling": "Muestreo",
}

_HEAD_FILL = PatternFill("solid", fgColor="1F3864")
_HEAD_FONT = Font(bold=True, color="FFFFFF")
_TITLE_FONT = Font(bold=True, size=14)
_TABLE_FONT = Font(bold=True, size=11)
_THIN = Side(style="thin", color="BFBFBF")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_INVALID_SHEET_CHARS = re.compile(r"[\[\]:*?/\\]")


def _cell(value: Any) -> Any:
    """Valor apto para una celda: None, número, texto o booleano convertido a Sí/No."""
    if isinstance(value, bool):
        return "Sí" if value else "No"
    if isinstance(value, (int, float, str)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        if len(value) == 1 and isinstance(value[0], (int, float)) and not isinstance(value[0], bool):
            return value[0]  # un solo número va como número, no como texto
        return ", ".join(str(_cell(v)) for v in value)
    if isinstance(value, dict):
        return "; ".join(f"{k}: {_cell(v)}" for k, v in value.items())
    return str(value)


def _put(ws: Worksheet, row: int, col: int, value: Any):
    """Escribe un valor: los números van como celdas numéricas con formato (nunca como texto) y
    los textos tal como llegan (uno que empiece con '=' no se interpreta como fórmula)."""
    c = ws.cell(row, col)
    if isinstance(value, str):
        c.value = value
        c.data_type = "s"
    else:
        c.value = value
        if isinstance(value, float):
            c.number_format = "0.0000" if abs(value) < 1000 else "#,##0.00"
        elif isinstance(value, int):
            c.number_format = "0"
    return c


class _Sheet:
    """Cursor de escritura sobre una hoja, con numeración global de tablas."""

    def __init__(self, ws: Worksheet, counter: list[int]):
        self.ws = ws
        self.row = 1
        self.counter = counter
        self.widths: dict[int, int] = {}

    def _track(self, col: int, value: Any) -> None:
        length = len(str(value)) if value is not None else 0
        self.widths[col] = min(max(self.widths.get(col, 8), length + 2), 60)

    def title(self, text: str) -> None:
        self.ws.cell(self.row, 1, text).font = _TITLE_FONT
        self.row += 2

    def text(self, label: str, value: Any = None, bold: bool = False) -> None:
        a = self.ws.cell(self.row, 1, label)
        a.font = Font(bold=bold or value is not None)
        if value is not None:
            self._track(1, label)
        if value is not None:
            _put(self.ws, self.row, 2, _cell(value))
            self._track(2, _cell(value))
        self.row += 1

    def blank(self) -> None:
        self.row += 1

    def paragraph(self, text: str) -> None:
        c = _put(self.ws, self.row, 1, text)
        c.alignment = Alignment(wrap_text=False, vertical="top")
        self.row += 1

    def table(self, title: str, headers: list[str], rows: Iterable[Iterable[Any]]) -> tuple[int, int, int]:
        """Escribe una tabla numerada. Devuelve (fila de encabezado, primera fila de datos, última)."""
        self.counter[0] += 1
        self.ws.cell(self.row, 1, f"Tabla {self.counter[0]}. {title}").font = _TABLE_FONT
        self.row += 1
        header_row = self.row
        for j, h in enumerate(headers, start=1):
            c = self.ws.cell(self.row, j, h)
            c.font, c.fill, c.border = _HEAD_FONT, _HEAD_FILL, _BORDER
            c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            self._track(j, h)
        self.row += 1
        first = self.row
        for r in rows:
            for j, v in enumerate(r, start=1):
                v = _cell(v)
                c = _put(self.ws, self.row, j, v)
                c.border = _BORDER
                self._track(j, v if not isinstance(v, float) else f"{v:.4f}")
            self.row += 1
        last = self.row - 1
        self.row += 1
        return header_row, first, last

    def interpretation(self, interp: Optional[dict]) -> None:
        if not interp:
            return
        self.ws.cell(self.row, 1, "Interpretación").font = _TABLE_FONT
        self.row += 1
        if interp.get("summary"):
            self.paragraph(str(interp["summary"]))
        for label, key in (("Hallazgos", "findings"), ("Advertencias", "warnings")):
            items = interp.get(key) or []
            if items:
                self.ws.cell(self.row, 1, label).font = Font(bold=True, italic=True)
                self.row += 1
                for item in items:
                    self.paragraph(f"• {item}")
        self.row += 1

    def chart(self, chart, anchor_col: int = 1, height_rows: int = 16) -> None:
        chart.width, chart.height = 24, 8.5
        self.ws.add_chart(chart, f"{get_column_letter(anchor_col)}{self.row}")
        self.row += height_rows

    def finish(self) -> None:
        for col, width in self.widths.items():
            self.ws.column_dimensions[get_column_letter(col)].width = max(width, 12)
        self.ws.column_dimensions["A"].width = max(self.ws.column_dimensions["A"].width or 0, 26)
        self.ws.column_dimensions["A"].width = min(self.ws.column_dimensions["A"].width, 46)


# --- Gráficos nativos -------------------------------------------------------------
def _line_chart(sheet: _Sheet, title: str, header_row: int, first: int, last: int, label_col: int,
                value_cols: list[int], y_title: str) -> None:
    ch = LineChart()
    ch.title, ch.y_axis.title, ch.x_axis.title = title, y_title, "Subgrupo"
    ch.x_axis.delete = ch.y_axis.delete = False
    for col in value_cols:
        ch.add_data(Reference(sheet.ws, min_col=col, min_row=header_row, max_row=last), titles_from_data=True)
    ch.set_categories(Reference(sheet.ws, min_col=label_col, min_row=first, max_row=last))
    for i, s in enumerate(ch.series):
        s.smooth = False
        if i == 0:
            s.marker.symbol = "circle"
        else:
            s.marker.symbol = "none"
            s.graphicalProperties.line.dashStyle = "dash"
    sheet.chart(ch)


def _scatter_chart(sheet: _Sheet, title: str, header_row: int, first: int, last: int, x_col: int,
                   y_cols: list[int], x_title: str, y_title: str, markers: bool = False) -> None:
    ch = ScatterChart()
    ch.title, ch.style = title, 13
    ch.x_axis.title, ch.y_axis.title = x_title, y_title
    ch.x_axis.delete = ch.y_axis.delete = False
    xs = Reference(sheet.ws, min_col=x_col, min_row=first, max_row=last)
    for col in y_cols:
        ys = Reference(sheet.ws, min_col=col, min_row=header_row, max_row=last)
        s = Series(ys, xs, title_from_data=True)
        s.marker.symbol = "circle" if markers else "none"
        s.smooth = False
        ch.series.append(s)
    sheet.chart(ch)


def _bar_chart(sheet: _Sheet, title: str, header_row: int, first: int, last: int, label_col: int,
               value_col: int, x_title: str, y_title: str) -> None:
    ch = BarChart()
    ch.type, ch.title, ch.gapWidth = "col", title, 10
    ch.x_axis.title, ch.y_axis.title = x_title, y_title
    ch.x_axis.delete = ch.y_axis.delete = False
    ch.add_data(Reference(sheet.ws, min_col=value_col, min_row=header_row, max_row=last), titles_from_data=True)
    ch.set_categories(Reference(sheet.ws, min_col=label_col, min_row=first, max_row=last))
    ch.legend = None
    sheet.chart(ch)


# --- Secciones por módulo ------------------------------------------------------------
def _g(d: Any, key: str, default: Any = None) -> Any:
    return d.get(key, default) if isinstance(d, dict) else default


def _descriptive_table(s: _Sheet, d: dict, title: str = "Estadística descriptiva global") -> None:
    names = [("count", "n"), ("mean", "Media"), ("std", "Desviación estándar"), ("min", "Mínimo"),
             ("q1", "Q1"), ("median", "Mediana"), ("q3", "Q3"), ("max", "Máximo"),
             ("skewness", "Asimetría"), ("kurtosis", "Curtosis (exceso)")]
    s.table(title, ["Estadístico", "Valor"], [(label, _g(d, k)) for k, label in names if k in d])


def _section_data(s: _Sheet, r: dict) -> None:
    if "overall" in r:
        _descriptive_table(s, r["overall"])
        s.table("Resumen por subgrupo", ["Subgrupo", "n", "Media", "Rango", "Desv. estándar", "Mínimo", "Máximo"],
                [(x["label"], x["n"], x["mean"], x["range"], x["std"], x["min"], x["max"]) for x in r["subgroups"]])
        out = r.get("outliers") or []
        s.table("Observaciones sospechosas (criterio 1.5·IQR)", ["Subgrupo (índice)", "Posición", "Valor", "Motivo"],
                [(o["subgroup_index"], o["position"], o["value"], o["reason"]) for o in out] or [("Ninguna", None, None, None)])
        s.text("Tamaño de subgrupo constante", r.get("constant_size"))
        s.blank()
    else:
        s.table("Resumen por subgrupo", ["Subgrupo", "Conteo", "Tamaño", "Tasa"],
                [(x["label"], x["count"], x["size"], x["rate"]) for x in r.get("rows", [])])
        s.table("Totales", ["Medida", "Valor"], [
            ("Subgrupos", r.get("subgroups")), ("Conteo total", r.get("total_count")),
            ("Tamaño total", r.get("total_size")), ("Tasa global", r.get("overall_rate")),
            ("Conteo promedio", r.get("mean_count")), ("Tamaño mínimo", r.get("min_size")),
            ("Tamaño máximo", r.get("max_size")), ("Tamaño constante", r.get("constant_size")),
        ])
        if r.get("warnings"):
            s.interpretation({"summary": "Advertencias de los datos", "warnings": r["warnings"]})


def _section_chart(s: _Sheet, r: dict) -> None:
    lim = r.get("limits", {})
    s.table("Estado del gráfico", ["Concepto", "Valor"], [
        ("Tipo de gráfico", r.get("chart_type")), ("Fase", r.get("phase")),
        ("En control", r.get("in_control")),
        ("Subgrupos con señal (índice base 0)", r.get("out_of_control_points") or "Ninguno"),
    ])
    params = lim.get("params", {})
    rows = [(k, v) for k, v in params.items()] + [
        ("Subgrupos usados", lim.get("points_used")), ("Tamaño de subgrupo", lim.get("subgroup_size")),
        ("Método de sigma", lim.get("sigma_method")), ("Ancho de límites L", lim.get("limit_width")),
    ]
    s.table("Parámetros del proceso y límites congelables", ["Parámetro", "Valor"], rows)
    if lim.get("excluded"):
        s.table("Puntos excluidos del cálculo de límites (Fase I)", ["Índice", "Etiqueta", "Causa asignable"],
                [(e["index"], e.get("label"), e["cause"]) for e in lim["excluded"]])
    for panel in r.get("charts", []):
        flagged = {v["index"] for v in panel.get("violations", [])}
        idx = panel.get("indices", [])
        rows = [(panel["labels"][k], panel["values"][k], panel["center"][k], panel["ucl"][k], panel["lcl"][k],
                 "Sí" if idx[k] in flagged else "") for k in range(len(panel["values"]))]
        h, a, b = s.table(f"Puntos graficados: {panel['title']}",
                          ["Subgrupo", "Valor", "Línea central", "LSC", "LIC", "Señal"], rows)
        if b >= a:
            _line_chart(s, panel["title"], h, a, b, 1, [2, 3, 4, 5], panel["title"])
        if panel.get("violations"):
            s.table(f"Señales detectadas: {panel['title']}", ["Regla", "Subgrupo (índice)", "Descripción"],
                    [(v["rule"], v["index"], v["description"]) for v in panel["violations"]])
        if panel.get("rules_skipped"):
            s.table(f"Reglas no evaluadas: {panel['title']}", ["Regla", "Motivo"],
                    [(x["rule"], x["reason"]) for x in panel["rules_skipped"]])


def _section_assumptions(s: _Sheet, r: dict) -> None:
    _descriptive_table(s, r["descriptive"])
    for key, title in (("normality", "Pruebas de normalidad"), ("independence", "Pruebas de independencia")):
        s.table(title, ["Prueba", "Hipótesis nula", "Estadístico", "Valor p", "Valor crítico", "Rechaza H0", "Conclusión"],
                [(t["name"], t["null_hypothesis"], t["statistic"], t.get("p_value"), t.get("critical_value"),
                  t["reject"], t["conclusion"]) for t in r.get(key, [])])
    s.table("Resultado global", ["Concepto", "Valor"],
            [("Normalidad no rechazada", r.get("is_normal")), ("Independencia no rechazada", r.get("is_independent"))])
    hist = r["histogram"]
    centers = [(hist["edges"][i] + hist["edges"][i + 1]) / 2 for i in range(len(hist["counts"]))]
    h, a, b = s.table("Histograma", ["Centro de clase", "Frecuencia"], zip(centers, hist["counts"]))
    if b >= a:
        _bar_chart(s, "Histograma", h, a, b, 1, 2, "Valor", "Frecuencia")
    h, a, b = s.table("Gráfico cuantil-cuantil normal", ["Cuantil teórico", "Valor observado"],
                      [(p["theoretical"], p["observed"]) for p in r.get("qq", [])])
    if b >= a:
        _scatter_chart(s, "Q-Q normal", h, a, b, 1, [2], "Cuantil teórico", "Observado", markers=True)
    ac = r["autocorrelation"]
    h, a, b = s.table("Autocorrelación", ["Rezago", "Autocorrelación"], zip(ac["lags"], ac["values"]))
    s.text("Banda de significancia ±", ac.get("band"))
    s.text("Rezagos significativos", ac.get("significant_lags") or "Ninguno")
    s.blank()
    if b >= a:
        _bar_chart(s, "Función de autocorrelación", h, a, b, 1, 2, "Rezago", "Autocorrelación")


def _index_rows(r: dict) -> list[tuple]:
    out = []
    for key, label in (("cp", "Cp"), ("cpl", "Cpl"), ("cpu", "Cpu"), ("cpk", "Cpk"), ("pp", "Pp"),
                       ("ppl", "Ppl"), ("ppu", "Ppu"), ("ppk", "Ppk"), ("cpm", "Cpm")):
        v = r.get(key) or {}
        out.append((label, v.get("value"), v.get("lower"), v.get("upper")))
    return out


def _section_capability(s: _Sheet, r: dict) -> None:
    s.table("Datos del análisis", ["Concepto", "Valor"], [
        ("Observaciones", r.get("n")), ("Media", r.get("mean")), ("Sigma corto plazo (within)", r.get("sigma_within")),
        ("Sigma largo plazo (overall)", r.get("sigma_overall")), ("Método de sigma", r.get("sigma_method")),
        ("Veredicto según Cpk", r.get("verdict")),
    ])
    s.table("Índices de capacidad", ["Índice", "Valor", "Límite inferior", "Límite superior"], _index_rows(r))
    nc = []
    for key, label in (("expected_within", "Esperado (sigma within)"), ("expected_overall", "Esperado (sigma overall)"),
                       ("observed", "Observado")):
        v = r.get(key) or {}
        nc.append((label, v.get("below_lsl"), v.get("above_usl"), v.get("total"), v.get("ppm")))
    s.table("Fracción fuera de especificación", ["Fuente", "Bajo LSL", "Sobre USL", "Total", "PPM"], nc)
    hist = r["histogram"]
    centers = [(hist["edges"][i] + hist["edges"][i + 1]) / 2 for i in range(len(hist["counts"]))]
    h, a, b = s.table("Histograma", ["Centro de clase", "Frecuencia"], zip(centers, hist["counts"]))
    if b >= a:
        _bar_chart(s, "Histograma del proceso", h, a, b, 1, 2, "Valor", "Frecuencia")


def _curve(s: _Sheet, title: str, points: list[dict], x_title: str, y_title: str, markers: bool = False) -> None:
    if not points:
        return
    h, a, b = s.table(title, [x_title, y_title], [(p["x"], p["y"]) for p in points])
    _scatter_chart(s, title, h, a, b, 1, [2], x_title, y_title, markers)


def _section_design(s: _Sheet, r: dict) -> None:
    if "method" in r:  # ArlResponse
        s.table("Resumen", ["Concepto", "Valor"], [
            ("Método", r.get("method")), ("Probabilidad de falsa alarma (alfa)", r.get("alpha")),
            ("ARL0", r.get("arl0")), ("Error estándar ARL0", r.get("arl0_std_error")), ("ATS0 (horas)", r.get("ats0")),
            ("Carga muestral (unidades por hora)", r.get("sampling_load")),
        ])
        s.table("Desempeño ante estados fuera de control",
                ["Desplazamiento", "Beta", "ARL1", "ATS1 (horas)", "Unidades hasta detectar", "Error estándar"],
                [(x["shift"], x.get("beta"), x["arl1"], x["ats1"], x["units_to_detect"], x.get("std_error"))
                 for x in r["rows"]])
        _curve(s, "Curva característica de operación", r.get("oc_curve", []), "Desplazamiento", "Beta")
        _curve(s, "Curva de ARL", r.get("arl_curve", []), "Desplazamiento", "ARL")
    else:  # CompareResponse
        s.text("Desplazamiento de interés (sigmas)", r.get("shift"))
        s.blank()
        s.table("Comparación de diseños", ["n", "L", "h (horas)", "ARL0", "ATS0", "ARL1", "ATS1", "Carga n/h"],
                [(x["n"], x["limit_width"], x["sampling_interval"], x["arl0"], x["ats0"], x["arl1"], x["ats1"],
                  x["sampling_load"]) for x in r["rows"]])


def _section_sampling(s: _Sheet, r: dict) -> None:
    if "n" in r:
        s.table("Plan simple", ["Concepto", "Valor"], [
            ("n", r["n"]), ("c", r["c"]), ("Distribución", r.get("distribution")),
            ("Riesgo del productor real (alfa)", r.get("alpha_actual")),
            ("Riesgo del consumidor real (beta)", r.get("beta_actual")),
            ("AOQL", r.get("aoql")), ("AOQL ocurre en p =", r.get("aoql_at")),
        ])
    else:
        s.table("Plan doble", ["Concepto", "Valor"], [
            ("Riesgo del productor real (alfa)", r.get("alpha_actual")),
            ("Riesgo del consumidor real (beta)", r.get("beta_actual")),
            ("AOQL", r.get("aoql")), ("AOQL ocurre en p =", r.get("aoql_at")),
        ])
    _curve(s, "Curva OC (probabilidad de aceptación)", r.get("oc_curve", []), "Fracción defectuosa", "Pa")
    _curve(s, "Curva AOQ", r.get("aoq_curve", []), "Fracción defectuosa", "AOQ")
    _curve(s, "Curva ATI (inspección total promedio)", r.get("ati_curve") or [], "Fracción defectuosa", "ATI")
    _curve(s, "Curva ASN (tamaño promedio de muestra)", r.get("asn_curve") or [], "Fracción defectuosa", "ASN")
    _curve(s, "Aceptación en la primera muestra", r.get("first_sample_accept_curve") or [], "Fracción defectuosa", "Pa")


_WRITERS = {
    "data": _section_data,
    "variables": _section_chart,
    "attributes": _section_chart,
    "assumptions": _section_assumptions,
    "capability": _section_capability,
    "design": _section_design,
    "sampling": _section_sampling,
}


def _sheet_name(base: str, used: set[str]) -> str:
    name = _INVALID_SHEET_CHARS.sub(" ", base).strip().strip("'")[:31] or "Hoja"
    candidate, k = name, 1
    while candidate.lower() in used:
        k += 1
        suffix = f" ({k})"
        candidate = name[: 31 - len(suffix)] + suffix
    used.add(candidate.lower())
    return candidate


def build_workbook(study: dict, sections: list[dict]) -> bytes:
    """Genera el libro y lo devuelve como bytes `.xlsx`."""
    wb = Workbook()
    cover_ws = wb.active
    cover_ws.title = "Portada"
    used = {"portada"}
    counter = [0]
    index: list[tuple[int, str, str, str, str]] = []

    names = [_sheet_name(f"{n}. {sec['title']}", used) for n, sec in enumerate(sections, start=1)]
    for n, (section, name) in enumerate(zip(sections, names), start=1):
        index.append((n, section["title"], MODULE_NAMES.get(section["module"], section["module"]), name,
                      section.get("created_at") or ""))

    cover = _Sheet(cover_ws, counter)
    cover.title("Reporte del estudio de Control Estadístico de Procesos")
    for label, key in (("Estudio", "name"), ("Empresa", "company"), ("Proceso", "process"), ("Producto", "product"),
                       ("Característica de calidad", "characteristic"), ("Unidad", "unit"),
                       ("Límite inferior de especificación (LSL)", "lsl"), ("Límite superior de especificación (USL)", "usl"),
                       ("Valor objetivo", "target"), ("Analista", "analyst")):
        if study.get(key) is not None and study.get(key) != "":
            cover.text(label, study[key])
    cover.text("Generado", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
    cover.blank()
    cover.table("Contenido del libro", ["N.º", "Análisis", "Módulo", "Hoja", "Fecha"], index)
    cover.paragraph("Datos generados por el software CEP; revise las interpretaciones antes de usarlas como conclusión final.")
    cover.finish()

    for section, name in zip(sections, names):
        module = section["module"]
        sheet_name = name
        s = _Sheet(wb.create_sheet(sheet_name), counter)
        s.title(section["title"])
        s.text("Módulo", MODULE_NAMES.get(module, module))
        if section.get("created_at"):
            s.text("Fecha del análisis", section["created_at"])
        s.blank()
        result = section.get("result") or {}
        s.interpretation(result.get("interpretation"))
        _WRITERS[module](s, result)
        s.finish()


    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
