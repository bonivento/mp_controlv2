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
    fmt_pct,
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
    # Coma decimal en los textos en español (hallazgo H12 del validador).
    assert fmt(370.398) == "370,4"
    assert fmt(0.0027) == "0,0027"
    assert fmt(None) == "no disponible"
    assert fmt(float("nan")) == "no disponible"
    assert fmt(123456.7) == "123 457"
    assert fmt_p(0.00001) == "< 0,0001"
    assert fmt_p(0.04567) == "0,0457"
    assert fmt_ppm(0.0027) == "2 700 PPM"
    assert fmt_ppm(1e-7) == "0,1 PPM"
    # Un positivo pequeño nunca sale como "0" (hallazgo H13): notación científica.
    assert fmt(1.2e-7) == "1,2·10⁻⁷"
    assert fmt(3.8e-8, 2) == "3,8·10⁻⁸"
    assert fmt(-0.4) == "-0,4"
    assert fmt_pct(1e-7) == "< 0,01 %"


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
    assert "370,4" in it.summary and "4,495" in it.summary
    assert any("Carga muestral: 10" in f for f in it.findings)
    small = compute_arl("individuals")
    assert any("lento para desplazamientos pequeños" in f for f in small.interpretation.findings)


def test_attribute_arl0_difference_is_explained():
    r = compute_arl("p", n=100, p0=0.02, p1=[0.05])
    it = r.interpretation
    _assert_clean(it)
    text = " ".join(it.findings)
    assert f"El ARL0 real es {fmt(r.arl0, 4)}" in text and "370,4" in text
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
    # Sin plan de referencia no se afirma qué propondría un nomograma (hallazgo H8).
    assert not any("nomograma" in f for f in it.findings)
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
    assert any("S4 (13,5)" in f and "causa asignable" in f for f in it.findings)


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


def test_phase_two_single_point_below_lcl_is_possible_improvement():
    """H12: un punto bajo el LCI de un gráfico de atributos no es "salió de control, actuar"."""
    vals = [0.10, 0.12, 0.09, 0.01, 0.11]
    viol = [{"rule": "WE1", "index": 3, "description": "bajo LCI"}]
    it = interpret_control_chart([_panel("p", vals, 0.10, 0.22, 0.02, viol)], phase="II", chart_type="p")
    _assert_clean(it)
    assert "posible mejora" in it.summary and "salió de control" not in it.summary
    assert "el subgrupo S4 queda" in it.summary
    assert any(f.startswith("El punto S4 queda por debajo del LCI") for f in it.findings)


def test_run_signal_in_asymmetric_panel_is_reported_with_caution():
    """H5: una racha en R no se afirma como "cambió la variabilidad"."""
    r_vals = [1.2] * 9 + [0.8]
    viol = [{"rule": "WE4", "index": 8, "description": "racha"}]
    charts = [_panel("xbar", [10.0] * 10, 10.0, 12.0, 8.0), _panel("r", r_vals, 1.0, 2.1, 0.0, viol)]
    it = interpret_control_chart(charts, phase="I", chart_type="xbar_r", rules=["WE1", "WE4"])
    text = " ".join(it.findings)
    assert "asimétrica" in text and "indicio" in text
    assert "indican que cambió la variabilidad" not in text


def test_n8_text_depends_on_sides():
    """N8 con los ocho puntos del mismo lado es un desplazamiento, no una mezcla."""
    viol = [{"rule": "N8", "index": 7, "description": "N8"}]
    same = interpret_control_chart([_panel("i", [1.5] * 8, 0.0, 3.0, -3.0, viol)], phase="I", chart_type="i_mr")
    assert any("desplazamiento del nivel" in f and "no una mezcla" in f for f in same.findings)
    both = interpret_control_chart([_panel("i", [1.5, -1.5] * 4, 0.0, 3.0, -3.0, viol)], phase="I",
                                   chart_type="i_mr")
    assert any("mezcla de dos poblaciones" in f for f in both.findings)


def test_phase_one_counts_retained_subgroups():
    from app.spc import phases

    r = phases.phase_one("c", [5, 6, 4, 30, 5, 6, 5, 4, 6, 5], excluded=[(3, "lote defectuoso")])
    it = interpret_chart_result(r, rules=["WE1"])
    assert "los 9 subgrupos retenidos están en control" in it.summary
    assert "se excluyó 1 subgrupo" in it.summary
    assert any("Se excluyó 1 subgrupo" in f and "Sigue graficado" in f for f in it.findings)


def test_weak_ljung_box_rejection_is_not_overstated():
    """H6: un rechazo aislado de Ljung-Box sin rezago 1 significativo es evidencia débil."""
    for seed in range(300):
        x = np.random.default_rng(seed).normal(size=120)
        res = analyze_assumptions(x)
        lb, runs = res.independence
        if lb.reject and not runs.reject and 1 not in res.autocorrelation.significant_lags \
                and len(res.autocorrelation.significant_lags) <= 1:
            break
    else:
        pytest.skip("no apareció el caso en 300 semillas")
    it = res.interpretation
    assert "débil" in it.summary and "autocorrelacionadas" in it.summary  # "No alcanza para afirmar…"
    assert "No alcanza para afirmar" in it.summary
    assert not any("AR(1)" in w for w in it.warnings)
    assert not any("autocorrelación positiva" in w for w in it.warnings)


# ------------------------------------------- tercera ronda (H18, H19, H24, H25, S6)


def test_order_rules_not_blamed_for_asymmetry():
    """H18: N3 depende solo del orden; el hallazgo de asimetría no la nombra."""
    viol = [{"rule": "N3", "index": 6, "description": "tendencia"}]
    charts = [_panel("xbar", [10.0] * 10, 10.0, 12.0, 8.0),
              _panel("r", [0.5, 0.7, 0.9, 1.1, 1.3, 1.5, 1.7, 1.0, 0.9, 1.0], 1.0, 2.1, 0.0, viol)]
    it = interpret_control_chart(charts, phase="I", chart_type="xbar_r", rules=["WE1", "N3"])
    assert not any("asimétrica" in f for f in it.findings)


def test_we4_with_integer_center_says_fewer_false_alarms():
    """H19: c̄ = 50/25 = 2, un valor posible: los empates cortan la racha (ARL0 de WE4
    1 924 según el validador, frente a 255)."""
    from app.spc import phases
    r = phases.phase_one("c", [1] * 8 + [3, 2] * 8 + [2], rules=["WE1", "WE4"])
    text = " ".join(interpret_chart_result(r, rules=["WE1", "WE4"]).findings)
    assert "menos falsas alarmas que la nominal" in text and "más a menudo" not in text
    # c̄ = 112/24 = 4,667, que no es un conteo posible: sin empates, más falsas alarmas.
    vals = [3] * 8 + [5, 6] * 8
    r2 = phases.phase_one("c", vals, rules=["WE1", "WE4"])
    assert any(v.rule == "WE4" for v in r2.charts[0].violations)
    text2 = " ".join(interpret_chart_result(r2, rules=["WE1", "WE4"]).findings)
    assert "más a menudo" in text2 and "no es un valor posible" in text2


def test_mr_signal_is_a_jump_not_subgroup_variability():
    """H24: en I-MR no hay subgrupos."""
    viol = [{"rule": "WE1", "index": 5, "description": "fuera"}]
    charts = [_panel("i", [10.0] * 10, 10.0, 13.0, 7.0),
              _panel("mr", [1.0, 1.0, 1.0, 1.0, 4.5, 1.0, 1.0, 1.0, 1.0], 1.13, 3.7, 0.0, viol)]
    it = interpret_control_chart(charts, phase="I", chart_type="i_mr", rules=["WE1"])
    text = _all_text(it)
    assert "subgrupo" not in text
    assert "salto grande entre dos observaciones consecutivas" in text


def test_constant_truncated_lcl_text():
    from app.spc import phases
    r = phases.phase_one("p", [3, 5, 2, 4, 3, 6], [80, 100, 90, 85, 100, 120])
    text = _all_text(interpret_chart_result(r))
    assert "LCI = 0 en todos los puntos" in text and "LCI entre 0 y 0" not in text


def test_many_rules_warning():
    """S6: con reglas suplementarias se advierte la tasa conjunta (WE1 a WE4: ARL0 91,75
    según Champ y Woodall, 1987; 12 reglas: 65,5 ± 0,9 simulado con compute_arl)."""
    charts = [_panel("i", [10.0] * 10, 10.0, 13.0, 7.0)]
    many = interpret_control_chart(charts, phase="I", chart_type="i_mr", rules=["WE1", "WE2", "WE3", "WE4"])
    assert any("reglas a la vez" in w and "92" in w for w in many.warnings)
    one = interpret_control_chart(charts, phase="I", chart_type="i_mr", rules=["WE1"])
    assert not any("reglas a la vez" in w for w in one.warnings)
