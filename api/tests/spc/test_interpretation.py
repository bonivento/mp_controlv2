"""Pruebas de la interpretación automática: textos con los números del caso,
sin NaN ni frases vacías, y coherentes con el resultado."""

import re
from dataclasses import asdict

import numpy as np
import pytest

from app.spc.assumptions import analyze_assumptions
from app.spc.capability import analyze_capability
from app.spc.design import compare_designs, compute_arl
from app.spc.interpretation import (
    Interpretation,
    fmt,
    fmt_p,
    fmt_ppm,
    interpret_chart_result,
    interpret_control_chart,
)
from app.spc.sampling import design_single_plan, evaluate_double_plan


def _all_text(it: Interpretation) -> str:
    return " ".join([it.summary, *it.findings, *it.warnings])


def _assert_clean(it: Interpretation):
    text = _all_text(it)
    assert it.summary.strip()
    assert not re.search(r"\bnan\b|\binf\b|None", text, re.IGNORECASE), text
    assert all(f.strip() for f in it.findings)


def test_number_formatting():
    assert fmt(370.398) == "370.4"
    assert fmt(0.0027) == "0.0027"
    assert fmt(None) == "no disponible"
    assert fmt(float("nan")) == "no disponible"
    assert fmt(123456.7) == "123 457"
    assert fmt_p(0.00001) == "< 0.0001"
    assert fmt_p(0.04567) == "0.0457"
    assert fmt_ppm(0.0027) == "2 700 PPM"
    assert fmt_ppm(1e-7) == "0.1 PPM"


def test_assumptions_interpretation_cites_tests_and_numbers():
    x = np.random.default_rng(1).exponential(size=120)
    res = analyze_assumptions(x)
    it = res.interpretation
    _assert_clean(it)
    assert "no normales" in it.summary or "no cumplen" in it.summary
    assert any("Shapiro-Wilk" in f and "W =" in f for f in it.findings)
    assert any("asimetría" in f for f in it.findings)
    assert "120" in it.summary


def test_capability_interpretation_explains_off_center_and_long_term():
    rng = np.random.default_rng(2)
    # Media desplazada hacia USL y deriva entre subgrupos.
    sg = (rng.normal(11.0, 0.3, (30, 5)) + rng.normal(0, 0.3, (30, 1))).tolist()
    res = analyze_capability(sg, lsl=9.0, usl=12.0, is_stable=True, is_normal=True)
    it = res.interpretation
    _assert_clean(it)
    assert any("descentrado" in f and "superior" in f for f in it.findings)
    assert any("largo plazo" in f and "Ppk" in f for f in it.findings)
    assert fmt(res.cpk.value, 3) in it.summary


def test_arl_interpretation_contains_case_numbers():
    r = compute_arl("xbar", n=5, sampling_interval=0.5)
    it = r.interpretation
    _assert_clean(it)
    assert "370.4" in it.summary and "4.495" in it.summary
    assert any("Carga muestral: 10" in f for f in it.findings)
    small = compute_arl("individuals")
    assert any("lento para desplazamientos pequeños" in f for f in small.interpretation.findings)


def test_attribute_arl0_difference_is_explained():
    r = compute_arl("p", n=100, p0=0.02, p1=[0.05])
    it = r.interpretation
    _assert_clean(it)
    text = " ".join(it.findings)
    assert f"El ARL0 real es {fmt(r.arl0, 4)}" in text and "370.4" in text
    assert "no puede señalar mejoras" in text


def test_compare_interpretation():
    res = compare_designs([1, 5], sampling_intervals=[0.2, 1.0])
    _assert_clean(res.interpretation)
    assert "n = 5" in res.interpretation.summary or "n = 1" in res.interpretation.summary


def test_sampling_interpretation_explains_nomograph():
    r = design_single_plan(0.01, 0.06, 0.05, 0.10, lot_size=10_000)
    it = r.interpretation
    _assert_clean(it)
    assert "n = 110, c = 3" in it.summary
    assert any("Con c = 2 el menor tamaño que cumple β es n = 88" in f for f in it.findings)
    assert any("AOQL" in f for f in it.findings)
    assert any("Inspección total promedio" in f for f in it.findings)
    d = evaluate_double_plan(50, 1, 4, 100, 3, aql=0.01, ltpd=0.06)
    _assert_clean(d.interpretation)
    assert any("ASN" in f for f in d.interpretation.findings)


def _panel(name, values, center, ucl, lcl, violations=(), excluded=()):
    m = len(values)
    return {
        "name": name,
        "title": name,
        "labels": [f"S{i + 1}" for i in range(m)],
        "values": values,
        "center": [center] * m,
        "ucl": [ucl] * m,
        "lcl": [lcl] * m,
        "violations": list(violations),
        "excluded": list(excluded),
    }


def test_control_chart_interpretation_phase_two_signal_from_dicts():
    vals = [10.0, 10.2, 9.9, 13.5, 10.1]
    viol = [{"rule": "WE1", "index": 3, "description": "fuera"}]
    charts = [_panel("xbar", vals, 10.0, 12.0, 8.0, viol), _panel("r", [1, 1.2, 0.8, 1.1, 0.9], 1.0, 2.1, 0.0)]
    it = interpret_control_chart(charts, phase="II", chart_type="xbar_r", rules=["WE1"])
    _assert_clean(it)
    assert "Fase II" in it.summary and "S4" in it.summary and "WE1" in it.summary
    assert any("S4 (13.5)" in f and "causa asignable" in f for f in it.findings)


def test_control_chart_interpretation_phase_one_in_control_with_exclusions():
    charts = [_panel("i", [5.0, 5.1, 4.9, 5.0], 5.0, 5.6, 4.4, excluded=[2])]
    limits = {"points_used": 25, "excluded": [{"index": 2, "cause": "Cambio de proveedor", "label": "S3"}]}
    it = interpret_control_chart(charts, phase="I", chart_type="i_mr", limits=limits)
    _assert_clean(it)
    assert "pueden congelarse" in it.summary
    assert any("Cambio de proveedor" in f for f in it.findings)


def test_control_chart_interpretation_with_phases_result():
    from app.spc import phases

    rng = np.random.default_rng(5)
    x = rng.normal(10, 1, (25, 5))
    x[7] += 3
    r = phases.phase_one("xbar_r", x.tolist(), rules=["WE1", "WE2", "WE3", "WE4"])
    it = interpret_chart_result(r, rules=["WE1", "WE2", "WE3", "WE4"])
    _assert_clean(it)
    assert "Fase I" in it.summary and "8" in it.summary
    assert any("regla WE1" in f for f in it.findings)
    # Las reglas de zonas no aplicadas en R quedan advertidas.
    assert any("WE2" in w for w in it.warnings)
