"""Un caso feliz (comparado con `spc`) y uno de validación fallida por ruta."""

import csv
from dataclasses import asdict
from pathlib import Path

import pytest

from app.spc import (
    assumptions as spc_assumptions,
    attributes,
    capability as spc_capability,
    design as spc_design,
    interpretation,
    phases,
    sampling as spc_sampling,
)

EJEMPLOS = Path(__file__).resolve().parents[3] / "data" / "ejemplos"


def _read(name):
    with open(EJEMPLOS / name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _subgroups(name, cols):
    return [[float(r[c]) for c in cols] for r in _read(name)]


XCOLS = ["x1", "x2", "x3", "x4", "x5"]
PHASE1 = _subgroups("sintetico_fase1.csv", XCOLS)
PHASE2 = _subgroups("sintetico_fase2.csv", XCOLS)


def _no_nonfinite(obj):
    if isinstance(obj, float):
        assert obj == obj and obj not in (float("inf"), float("-inf"))
    elif isinstance(obj, dict):
        for v in obj.values():
            _no_nonfinite(v)
    elif isinstance(obj, list):
        for v in obj:
            _no_nonfinite(v)


def _expected_chart(result, rules=("WE1",)):
    payload = result.to_contract()
    payload["interpretation"] = asdict(interpretation.interpret_chart_result(result, rules=list(rules)))
    return payload


# --- Gráficos de variables ----------------------------------------------------
def test_variables_phase_one_matches_spc(client):
    excluded = [{"index": 11, "cause": "Boquilla obstruida"}]
    r = client.post("/api/charts/variables", json={
        "chart_type": "xbar_r", "phase": "I", "subgroups": PHASE1, "excluded": excluded})
    assert r.status_code == 200, r.text
    direct = phases.phase_one("xbar_r", PHASE1, excluded=excluded, limit_width=3.0, rules=["WE1"], labels=None)
    assert r.json() == _expected_chart(direct)
    assert r.json()["limits"]["points_used"] == 24
    _no_nonfinite(r.json())


def test_variables_phase_two_detects_shift_without_recalculating(client):
    p1 = client.post("/api/charts/variables", json={
        "chart_type": "xbar_r", "phase": "I", "subgroups": PHASE1,
        "excluded": [{"index": 11, "cause": "Boquilla obstruida"}]}).json()
    r = client.post("/api/charts/variables", json={
        "chart_type": "xbar_r", "phase": "II", "subgroups": PHASE2, "limits": p1["limits"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["limits"] == p1["limits"]
    assert body["in_control"] is False and len(body["out_of_control_points"]) >= 5
    direct = phases.phase_two("xbar_r", PHASE2, p1["limits"], rules=["WE1"], labels=None)
    assert body["out_of_control_points"] == direct.out_of_control_points


def test_variables_phase_two_without_limits(client):
    r = client.post("/api/charts/variables", json={"chart_type": "xbar_r", "phase": "II", "subgroups": PHASE2})
    assert r.status_code == 422 and r.json()["code"] == "missing_limits"


def test_variables_phase_two_with_exclusions_is_rejected_in_spanish(client):
    r = client.post("/api/charts/variables", json={
        "chart_type": "xbar_r", "phase": "II", "subgroups": PHASE2,
        "excluded": [{"index": 1, "cause": "x"}],
        "limits": {"chart_type": "xbar_r", "params": {"mu": 500, "sigma": 1}, "points_used": 5}})
    assert r.status_code == 422
    assert r.json()["code"] == "invalid_data"
    assert "Fase II" in r.json()["detail"] and "Value error" not in r.json()["detail"]


def test_variables_validation_errors_are_error_response(client):
    r = client.post("/api/charts/variables", json={"chart_type": "zzz", "phase": "I", "subgroups": [[1.0, 2.0]]})
    assert r.status_code == 422
    body = r.json()
    assert set(body) == {"detail", "code"} and body["code"] == "invalid_data"
    assert "chart_type" in body["detail"] and "subgroups" in body["detail"]
    r = client.post("/api/charts/variables", json={
        "chart_type": "xbar_r", "phase": "I", "subgroups": [[1.0, 2.0], [1.0]]})
    assert r.status_code == 422 and r.json()["code"] == "invalid_data"


def test_variables_rules_and_labels_pass_through(client):
    labels = [f"S{i}" for i in range(len(PHASE1))]
    r = client.post("/api/charts/variables", json={
        "chart_type": "xbar_r", "phase": "I", "subgroups": PHASE1, "labels": labels,
        "rules": {"enabled": ["WE1", "WE2", "N2"]}})
    assert r.status_code == 200
    assert r.json()["charts"][0]["labels"][0] == "S0"
    assert r.json()["charts"][0]["rules_applied"] == ["WE1", "WE2", "N2"]


def test_i_mr_chart(client):
    vals = [[float(r["valor"])] for r in _read("sintetico_i_mr.csv")]
    r = client.post("/api/charts/variables", json={"chart_type": "i_mr", "phase": "I", "subgroups": vals})
    assert r.status_code == 200
    mr = r.json()["charts"][1]
    assert len(mr["values"]) == len(vals) - 1 and mr["indices"][0] == 1


# --- Gráficos de atributos ---------------------------------------------------------
def test_attributes_phase_one_matches_spc(client):
    rows = _read("sintetico_p_n_variable.csv")
    cols = list(rows[0])
    count_col = next(c for c in cols if c not in ("fecha", "turno", "subgrupo") and "tamano" not in c)
    counts = [float(r[count_col]) for r in rows]
    sizes = [float(r["tamano_muestra"]) for r in rows]
    r = client.post("/api/charts/attributes", json={"chart_type": "p", "phase": "I", "counts": counts, "sizes": sizes})
    assert r.status_code == 200, r.text
    direct = phases.phase_one("p", counts, sizes, excluded=[], limit_width=3.0, rules=["WE1"], labels=None)
    assert r.json() == _expected_chart(direct)
    assert r.json()["out_of_control_points"] == [7, 19]


def test_attributes_phase_two_and_validation(client):
    counts = [2.0, 3.0, 1.0, 4.0, 2.0, 9.0]
    p1 = client.post("/api/charts/attributes", json={"chart_type": "c", "phase": "I", "counts": counts}).json()
    r = client.post("/api/charts/attributes", json={
        "chart_type": "c", "phase": "II", "counts": [2.0, 12.0], "limits": p1["limits"]})
    assert r.status_code == 200 and r.json()["out_of_control_points"] == [1]
    r = client.post("/api/charts/attributes", json={"chart_type": "c", "phase": "II", "counts": [2.0, 3.0]})
    assert r.json()["code"] == "missing_limits"
    r = client.post("/api/charts/attributes", json={"chart_type": "p", "phase": "I", "counts": [1.0, 2.0]})
    assert r.status_code == 422 and r.json()["code"] == "invalid_data"


def test_recommend(client):
    r = client.post("/api/charts/attributes/recommend", json={"counting": "defectives", "constant_size": False})
    assert r.status_code == 200
    assert r.json() == asdict(attributes.recommend_chart("defectives", False))
    r = client.post("/api/charts/attributes/recommend", json={"counting": "otro", "constant_size": True})
    assert r.status_code == 422 and r.json()["code"] == "invalid_data"


# --- Supuestos --------------------------------------------------------------------------
def test_assumptions(client):
    vals = [float(r["valor"]) for r in _read("sintetico_no_normal.csv")]
    r = client.post("/api/assumptions", json={"values": vals, "alpha": 0.05})
    assert r.status_code == 200, r.text
    assert r.json() == asdict(spc_assumptions.analyze_assumptions(vals, 0.05, None, None))
    assert r.json()["is_normal"] is False
    _no_nonfinite(r.json())


def test_assumptions_validation(client):
    r = client.post("/api/assumptions", json={"values": [1.0, 2.0]})
    assert r.status_code == 422 and r.json()["code"] == "invalid_data"
    r = client.post("/api/assumptions", json={"values": [5.0] * 10})  # sin variación: error de spc
    assert r.status_code == 422 and r.json()["detail"]


# --- Capacidad -----------------------------------------------------------------------------
def test_capability(client):
    subs = _subgroups("sintetico_xbar_r_en_control.csv", XCOLS)
    r = client.post("/api/capability", json={"subgroups": subs, "lsl": 495, "usl": 505, "target": 500})
    assert r.status_code == 200, r.text
    assert r.json() == asdict(spc_capability.analyze_capability(subs, lsl=495, usl=505, target=500))
    assert r.json()["verdict"] in ("marginal", "adequate", "excellent")
    _no_nonfinite(r.json())


def test_capability_validation(client):
    subs = [[1.0, 2.0], [2.0, 3.0]]
    assert client.post("/api/capability", json={"subgroups": subs}).status_code == 422
    r = client.post("/api/capability", json={"subgroups": subs, "lsl": 5, "usl": 1})
    assert r.status_code == 422 and "LSL" in r.json()["detail"]


# --- Diseño --------------------------------------------------------------------------------------
def test_design_arl(client):
    r = client.post("/api/design/arl", json={"chart": "xbar", "n": 5})
    assert r.status_code == 200, r.text
    assert r.json() == asdict(spc_design.compute_arl("xbar", n=5))
    assert r.json()["arl0"] == pytest.approx(370.4, abs=0.1)


def test_design_arl_simulation_is_reproducible(client):
    body = {"chart": "xbar", "n": 4, "rules": {"enabled": ["WE1", "WE2"]}, "max_runs": 200, "max_length": 2000}
    a, b = client.post("/api/design/arl", json=body), client.post("/api/design/arl", json=body)
    assert a.status_code == 200 and a.json()["method"] == "simulation" and a.json() == b.json()


def test_design_arl_validation(client):
    r = client.post("/api/design/arl", json={"chart": "p", "n": 50})  # falta p0
    assert r.status_code == 422 and r.json()["code"] == "invalid_data" and r.json()["detail"]
    assert client.post("/api/design/arl", json={"chart": "zzz"}).status_code == 422


def test_design_compare(client):
    r = client.post("/api/design/compare", json={"n_values": [3, 5], "limit_widths": [3.0, 2.5], "shift": 1.0})
    assert r.status_code == 200
    assert r.json() == asdict(spc_design.compare_designs([3, 5], [3.0, 2.5], [1.0], 1.0))
    assert len(r.json()["rows"]) == 4
    assert client.post("/api/design/compare", json={"n_values": []}).status_code == 422
    assert client.post("/api/design/compare", json={"n_values": [0]}).status_code == 422


# --- Muestreo --------------------------------------------------------------------------------------
def test_single_design_with_reference_plan(client):
    body = {"aql": 0.01, "ltpd": 0.06, "lot_size": 1000, "reference_plan": {"n": 100, "c": 2}}
    r = client.post("/api/sampling/single/design", json=body)
    assert r.status_code == 200, r.text
    direct = asdict(spc_sampling.design_single_plan(0.01, 0.06, 0.05, 0.10, 1000, "binomial", (100, 2)))
    assert r.json() == direct
    _no_nonfinite(r.json())


def test_single_design_validation(client):
    r = client.post("/api/sampling/single/design", json={"aql": 0.06, "ltpd": 0.01})
    assert r.status_code == 422 and r.json()["detail"]
    r = client.post("/api/sampling/single/design", json={"aql": 0.01, "ltpd": 0.06, "distribution": "hypergeometric"})
    assert r.status_code == 422 and r.json()["code"] == "invalid_data"


def test_single_evaluate(client):
    r = client.post("/api/sampling/single/evaluate", json={"n": 80, "c": 2, "aql": 0.01, "ltpd": 0.06, "lot_size": 500})
    assert r.status_code == 200
    assert r.json() == asdict(spc_sampling.evaluate_single_plan(80, 2, 500, "binomial", 0.01, 0.06))
    assert client.post("/api/sampling/single/evaluate", json={"n": 0, "c": 2}).status_code == 422


def test_double_evaluate(client):
    body = {"n1": 50, "c1": 1, "r1": 4, "n2": 50, "c2": 3, "lot_size": 1000, "aql": 0.01, "ltpd": 0.08}
    r = client.post("/api/sampling/double/evaluate", json=body)
    assert r.status_code == 200, r.text
    assert r.json() == asdict(spc_sampling.evaluate_double_plan(50, 1, 4, 50, 3, 1000, 0.01, 0.08))
    r = client.post("/api/sampling/double/evaluate", json={**body, "r1": 1})  # r1 <= c1
    assert r.status_code == 422 and r.json()["code"] == "invalid_data"


def test_unknown_field_is_rejected_in_spanish(client):
    r = client.post("/api/charts/attributes/recommend", json={"counting": "defects", "constant_size": True, "x": 1})
    assert r.status_code == 422 and "no reconocido" in r.json()["detail"]
