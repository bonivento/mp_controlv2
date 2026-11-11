import io
from dataclasses import asdict
from pathlib import Path

import openpyxl
import pytest

from app.spc import descriptive

EJEMPLOS = Path(__file__).resolve().parents[3] / "data" / "ejemplos"
FILES = sorted(EJEMPLOS.glob("sintetico_*.*"))
SUBS = [[10.1, 10.3, 9.9], [10.0, 10.2, 10.4], [9.8, 10.1, 10.0], [10.5, 10.2, 10.3]]


def _upload(client, name, content, ctype="application/octet-stream"):
    return client.post("/api/data/parse", files={"file": (name, content, ctype)})


def test_there_are_example_files():
    assert len(FILES) == 26


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_parse_every_example(client, path):
    r = _upload(client, path.name, path.read_bytes())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["filename"] == path.name
    sheet = body["sheets"][0]
    assert sheet["name"] == ("CSV" if path.suffix == ".csv" else "datos")
    assert len(sheet["rows"]) > 5
    assert all(len(row) == len(sheet["columns"]) for row in sheet["rows"])


@pytest.mark.parametrize("ext", ["csv", "xlsx"])
def test_parse_dirty_file(client, ext):
    path = EJEMPLOS / f"sintetico_sucio.{ext}"
    sheet = _upload(client, path.name, path.read_bytes()).json()["sheets"][0]
    cols = {c["name"]: c for c in sheet["columns"]}
    assert cols["x1"]["kind"] == "numeric" and cols["x1"]["missing"] == 1  # "N/D"
    assert cols["x2"]["missing"] == 1 and cols["x4"]["missing"] == 1  # celdas vacías
    assert cols["turno"]["kind"] == "text" and cols["turno"]["missing"] == 1
    assert cols["fecha"]["kind"] == "datetime"
    names = [c["name"] for c in sheet["columns"]]
    rows = sheet["rows"]
    assert rows[13][names.index("x3")] == 500.8  # coma decimal
    assert rows[16][names.index("x5")] == 497.7
    assert rows[8][names.index("x5")] == 5050.0  # el atípico no se borra
    assert rows[4][names.index("turno")] == "Tarde"  # espacios recortados
    assert rows[11][names.index("fecha")] == "2026-03-05"  # día/mes/año


def test_parse_csv_variants(client):
    semi = "a;b\n1,5;x\n2,5;y\n3,0;z\n".encode()
    s = _upload(client, "m.csv", semi).json()["sheets"][0]
    assert [r[0] for r in s["rows"]] == [1.5, 2.5, 3.0] and s["columns"][0]["kind"] == "numeric"
    tab = "a\tb\n1.5\tx\n2.5\ty\n".encode("utf-8")
    s = _upload(client, "m.csv", tab).json()["sheets"][0]
    assert len(s["columns"]) == 2 and s["rows"][1][0] == 2.5
    comma_dec = 'a,b\n"1,5",x\n"2,5",y\n'.encode("utf-8")
    assert _upload(client, "m.csv", comma_dec).json()["sheets"][0]["rows"][0][0] == 1.5
    latin = "dato,nota\n1,ñandú\n2,año\n".encode("cp1252")
    assert _upload(client, "m.csv", latin).json()["sheets"][0]["rows"][0][1] == "ñandú"


def test_parse_rejections(client):
    assert _upload(client, "m.pdf", b"x").status_code == 422
    assert _upload(client, "m.pdf", b"x").json()["code"] == "unsupported_file"
    assert _upload(client, "m.csv", b"").json()["code"] == "invalid_data"
    big = b"a,b\n" + b"1,2\n" * (1024 * 1024)
    r = _upload(client, "m.csv", big)
    assert r.status_code == 422 and "4 MB" in r.json()["detail"]
    many = ("a\n" + "1\n" * 20_001).encode()
    r = _upload(client, "m.csv", many)
    assert r.status_code == 422 and "20" in r.json()["detail"]
    r = _upload(client, "m.xlsx", b"no es un excel")
    assert r.status_code == 422 and r.json()["code"] == "unsupported_file"
    assert client.post("/api/data/parse").status_code == 422  # sin archivo


def test_parse_xlsx_multiple_sheets_and_row_limit(client):
    wb = openpyxl.Workbook()
    wb.active.title = "uno"
    wb.active.append(["v"])
    wb.active.append([1])
    two = wb.create_sheet("dos")
    two.append(["t"])
    two.append(["hola"])
    buf = io.BytesIO()
    wb.save(buf)
    sheets = _upload(client, "m.xlsx", buf.getvalue()).json()["sheets"]
    assert [s["name"] for s in sheets] == ["uno", "dos"]

    wb = openpyxl.Workbook(write_only=True)
    ws = wb.create_sheet("g")
    ws.append(["v"])
    for i in range(20_001):
        ws.append([i])
    buf = io.BytesIO()
    wb.save(buf)
    assert _upload(client, "g.xlsx", buf.getvalue()).status_code == 422


def test_summary_matches_spc(client):
    r = client.post("/api/data/summary", json={"subgroups": SUBS})
    assert r.status_code == 200
    expected = asdict(descriptive.summarize(SUBS, None))
    body = r.json()
    assert body["overall"]["mean"] == pytest.approx(expected["overall"]["mean"])
    assert body["constant_size"] is True
    assert [g["n"] for g in body["subgroups"]] == [3, 3, 3, 3]


def test_summary_validation(client):
    r = client.post("/api/data/summary", json={"subgroups": []})
    assert r.status_code == 422 and r.json()["code"] == "invalid_data"
    assert "subgroups" in r.json()["detail"]


def test_attribute_summary(client):
    r = client.post("/api/data/summary/attributes", json={
        "counts": [3, -1, 12, 5], "sizes": [100, 100, 0, 4], "labels": ["a", "b", "c", "d"]})
    assert r.status_code == 200
    b = r.json()
    assert b["subgroups"] == 4 and b["total_count"] == 19 and b["total_size"] == 204
    assert b["overall_rate"] == pytest.approx(19 / 204)
    assert b["mean_count"] == pytest.approx(19 / 4)
    assert (b["min_size"], b["max_size"], b["constant_size"]) == (0, 100, False)
    assert b["rows"][0]["rate"] == pytest.approx(0.03) and b["rows"][2]["rate"] is None
    text = " ".join(b["warnings"])
    assert "negativos" in text and "cero" in text and "mayor que el tamaño" in text


def test_attribute_summary_without_sizes_and_validation(client):
    b = client.post("/api/data/summary/attributes", json={"counts": [2, 3, 4]}).json()
    assert b["total_size"] is None and b["overall_rate"] is None and b["constant_size"] is None
    assert b["rows"][0]["label"] == "1" and b["warnings"] == []
    r = client.post("/api/data/summary/attributes", json={"counts": [1, 2], "sizes": [10]})
    assert r.status_code == 422 and "tamaños" in r.json()["detail"]
