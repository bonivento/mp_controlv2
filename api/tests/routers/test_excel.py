import io
from pathlib import Path

import openpyxl
import pytest

from tests.routers.test_analysis_routes import PHASE1, _read

EJEMPLOS = Path(__file__).resolve().parents[3] / "data" / "ejemplos"


@pytest.fixture()
def sections(client):
    def post(path, body):
        r = client.post(path, json=body)
        assert r.status_code == 200, (path, r.text)
        return r.json()

    values = [float(r["valor"]) for r in _read("sintetico_no_normal.csv")]
    return [
        {"module": "data", "title": "Resumen de datos", "result": post("/api/data/summary", {"subgroups": PHASE1})},
        {"module": "variables", "title": "X-barra R Fase I", "result": post("/api/charts/variables", {
            "chart_type": "xbar_r", "phase": "I", "subgroups": PHASE1})},
        {"module": "attributes", "title": "Gráfico c", "result": post("/api/charts/attributes", {
            "chart_type": "c", "phase": "I", "counts": [2, 3, 1, 4, 2, 5]})},
        {"module": "assumptions", "title": "Supuestos", "result": post("/api/assumptions", {"values": values})},
        {"module": "capability", "title": "Capacidad", "result": post("/api/capability", {
            "subgroups": PHASE1, "lsl": 495, "usl": 505})},
        {"module": "design", "title": "ARL X-barra", "result": post("/api/design/arl", {"chart": "xbar", "n": 5})},
        {"module": "design", "title": "Comparación", "result": post("/api/design/compare", {"n_values": [3, 5]})},
        {"module": "sampling", "title": "Plan simple", "result": post("/api/sampling/single/design", {
            "aql": 0.01, "ltpd": 0.06, "lot_size": 1000})},
        {"module": "sampling", "title": "Plan doble", "result": post("/api/sampling/double/evaluate", {
            "n1": 50, "c1": 1, "r1": 4, "n2": 50, "c2": 3})},
    ]


def test_excel_report_opens_with_expected_sheets(client, sections):
    study = {"name": "Llenado de salsa (sintético)", "company": "Empresa ficticia", "lsl": 495, "usl": 505, "unit": "g"}
    r = client.post("/api/reports/excel", json={"study": study, "sections": sections})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    assert "attachment" in r.headers["content-disposition"] and ".xlsx" in r.headers["content-disposition"]

    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames[0] == "Portada"
    assert len(wb.sheetnames) == 1 + len(sections)
    assert wb.sheetnames[1] == "1. Resumen de datos"
    assert all(len(n) <= 31 for n in wb.sheetnames)

    cover = [[c for c in row if c is not None] for row in wb["Portada"].iter_rows(values_only=True)]
    flat = [str(c) for row in cover for c in row]
    assert "Llenado de salsa (sintético)" in flat and "Empresa ficticia" in flat
    assert any(c.startswith("Tabla 1.") for c in flat)

    # Tablas numeradas con título en todas las hojas, interpretación donde aplica, gráfico nativo donde aplica.
    for ws in wb.worksheets[1:]:
        titles = [c.value for row in ws.iter_rows(max_col=1) for c in row if isinstance(c.value, str)]
        assert any(t.startswith("Tabla ") for t in titles), ws.title
    chart_sheet = wb["2. X-barra R Fase I"]
    assert len(chart_sheet._charts) == 2
    texts = [c.value for row in chart_sheet.iter_rows(max_col=1) for c in row if isinstance(c.value, str)]
    assert "Interpretación" in texts
    assert len(wb["5. Capacidad"]._charts) >= 1
    assert len(wb["8. Plan simple"]._charts) >= 1

    numbers = [int(t.split(".")[0].removeprefix("Tabla ")) for ws in wb.worksheets
               for row in ws.iter_rows(max_col=1) for c in row
               if isinstance((t := c.value), str) and t.startswith("Tabla ")]
    assert len(numbers) == len(set(numbers))  # cada número de tabla es único en el libro


def test_excel_report_validation(client):
    r = client.post("/api/reports/excel", json={"study": {"name": "x"}, "sections": []})
    assert r.status_code == 422 and r.json()["code"] == "invalid_data"
    r = client.post("/api/reports/excel", json={"study": {"name": "x"}, "sections": [
        {"module": "otro", "title": "t", "result": {}}]})
    assert r.status_code == 422
