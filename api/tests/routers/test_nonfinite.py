"""Números no finitos: se rechazan en la validación con `ErrorResponse` en español, y ninguna ruta
responde 500 con los archivos de ejemplo ni con casos límite."""

import csv
from pathlib import Path

import pytest

EJEMPLOS = Path(__file__).resolve().parents[3] / "data" / "ejemplos"
JSON = {"content-type": "application/json"}


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
def test_json_literals_are_rejected_with_readable_detail(client, literal):
    body = '{"subgroups": [[1, 2], [2, 3]], "lsl": %s, "usl": 5}' % literal
    r = client.post("/api/capability", content=body, headers=JSON)
    assert r.status_code == 422
    assert r.json() == {"detail": "Datos inválidos. lsl: debe ser un número finito.", "code": "invalid_data"}


def test_non_finite_inside_lists_and_overflow(client):
    r = client.post("/api/capability", content='{"subgroups": [[1, 2], [2, NaN]], "usl": 5}', headers=JSON)
    assert r.status_code == 422 and r.json()["detail"] == "Datos inválidos. subgroups.1.1: debe ser un número finito."
    r = client.post("/api/capability", content='{"subgroups": [[1, 2], [2, 3]], "lsl": 1e999, "usl": 5}', headers=JSON)
    assert r.status_code == 422 and "lsl: debe ser un número finito" in r.json()["detail"]
    r = client.post("/api/design/arl", content='{"chart": "xbar", "limit_width": Infinity}', headers=JSON)
    assert r.status_code == 422 and r.json()["code"] == "invalid_data"
    assert "limit_width: debe ser un número finito" in r.json()["detail"]


def test_edge_cases_do_not_return_500(client):
    constant = [[10.0, 10.0]] * 3
    calls = [
        ("/api/capability", {"subgroups": constant, "lsl": 9, "usl": 11}),
        ("/api/capability", {"subgroups": [[10, 10.1], [10.2, 9.9], [10, 10]], "lsl": 9}),
        ("/api/charts/variables", {"chart_type": "xbar_r", "phase": "I", "subgroups": constant}),
        ("/api/charts/variables", {"chart_type": "i_mr", "phase": "I", "subgroups": [[5.0]] * 3}),
        ("/api/charts/attributes", {"chart_type": "p", "phase": "I", "counts": [0, 0, 0], "sizes": [10, 10, 10]}),
        ("/api/charts/attributes", {"chart_type": "u", "phase": "I", "counts": [0, 0, 0], "sizes": [0, 0, 0]}),
        ("/api/charts/attributes", {"chart_type": "c", "phase": "I", "counts": [0, 0, 0]}),
        ("/api/data/summary", {"subgroups": [[5.0]]}),
        ("/api/data/summary/attributes", {"counts": [0, 0], "sizes": [0, 0]}),
        ("/api/design/arl", {"chart": "xbar", "n": 5, "shifts": [0, 0.0001, 100]}),
        ("/api/sampling/single/evaluate", {"n": 50, "c": 0, "lot_size": 50}),
        ("/api/sampling/single/evaluate", {"n": 5, "c": 10}),
    ]
    for url, body in calls:
        r = client.post(url, json=body)
        assert r.status_code < 500, (url, body, r.text)
        if r.status_code == 422:
            assert set(r.json()) == {"detail", "code"}


@pytest.mark.parametrize("path", sorted(EJEMPLOS.glob("sintetico_*.csv")), ids=lambda p: p.name)
def test_examples_never_return_500(client, path):
    if "sucio" in path.name:
        pytest.skip("tiene celdas vacías: se limpia antes de calcular")
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    keys = list(rows[0])
    xs = [k for k in keys if k[0] == "x" and k[1:].isdigit()]
    all_rules = {"enabled": ["WE1", "WE2", "WE3", "WE4", "N1", "N2", "N3", "N4", "N5", "N6", "N7", "N8"]}
    calls = []
    if xs:
        sg = [[float(r[k]) for k in xs] for r in rows]
        for ct in ("xbar_r", "xbar_s"):
            calls.append(("/api/charts/variables", {"chart_type": ct, "phase": "I", "subgroups": sg, "rules": all_rules}))
        calls += [("/api/capability", {"subgroups": sg, "lsl": 495, "usl": 505}),
                  ("/api/capability", {"subgroups": sg, "usl": 505}),
                  ("/api/data/summary", {"subgroups": sg}),
                  ("/api/assumptions", {"values": [v for s in sg for v in s]})]
    if "valor" in keys:
        v = [float(r["valor"]) for r in rows]
        calls += [("/api/charts/variables", {"chart_type": "i_mr", "phase": "I", "subgroups": [[x] for x in v], "rules": all_rules}),
                  ("/api/assumptions", {"values": v}),
                  ("/api/capability", {"subgroups": [[x] for x in v], "lsl": 0.1, "usl": 100})]
    count = next((k for k in ("defectuosos", "defectos") if k in keys), None)
    if count:
        counts = [float(r[count]) for r in rows]
        size_key = next((k for k in keys if "tamano" in k or "unidades" in k), None)
        sizes = [float(r[size_key]) for r in rows] if size_key else None
        calls.append(("/api/data/summary/attributes", {"counts": counts, "sizes": sizes}))
        for ct in ("p", "np", "c", "u"):
            body = {"chart_type": ct, "phase": "I", "counts": counts}
            if ct in ("p", "np", "u"):
                body["sizes"] = sizes or [100.0] * len(counts)
            calls.append(("/api/charts/attributes", body))
    assert calls
    for url, body in calls:
        r = client.post(url, json=body)
        assert r.status_code < 500, (path.name, url, r.text)
