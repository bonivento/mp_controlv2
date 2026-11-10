"""Pruebas de diseño de gráficos: ARL, ATS, curvas OC, simulación y comparación.

Valores de referencia:
- ARL0 = 1/(2Φ(-3)) = 370.4 con L = 3 (Montgomery, cap. 5 y 6).
- ARL1 para un desplazamiento de 1σ: 43.9 con n = 1 y 4.5 con n = 5
  (Montgomery, cap. 6, función OC y ARL del gráfico X-barra).
- Gráfico p con n = 50, p = 0.20, LCS = 0.3697, LCI = 0.0303
  (Montgomery, cap. 7, cálculo de la curva OC del gráfico p):
  β = P(D <= 18) - P(D <= 1).
- Gráfico c de tarjetas de circuito impreso, c̄ = 19.85, LCS = 33.22,
  LCI = 6.48 (Montgomery, cap. 7, Ejemplo 7.3 de la 6.ª ed.):
  β = P(x <= 33) - P(x <= 6).
"""

import math
import time
from dataclasses import asdict

import numpy as np
import pytest
from scipy import stats

from app.schemas.design import ArlResponse, CompareResponse
from app.spc import design
from app.spc.design import (
    c_chart_model,
    compare_designs,
    compute_arl,
    count_chart_beta,
    p_chart_model,
    xbar_beta,
    xbar_signal_probability,
)


# ------------------------------------------------------------------- exacto


def test_arl0_three_sigma():
    r = compute_arl("xbar", n=5)
    assert r.method == "exact"
    assert r.arl0 == pytest.approx(370.4, abs=0.05)
    assert r.alpha == pytest.approx(2 * stats.norm.cdf(-3))


def test_arl1_one_sigma_shift_n1_and_n5():
    r1 = compute_arl("individuals", shifts=[1.0])
    assert r1.rows[0].arl1 == pytest.approx(43.9, abs=0.05)
    r5 = compute_arl("xbar", n=5, shifts=[1.0])
    assert r5.rows[0].arl1 == pytest.approx(4.5, abs=0.01)
    # β a mano: Φ(3 - √5) - Φ(-3 - √5) = Φ(0.7639) - Φ(-5.236) ≈ 0.7775.
    assert r5.rows[0].beta == pytest.approx(
        stats.norm.cdf(3 - math.sqrt(5)) - stats.norm.cdf(-3 - math.sqrt(5))
    )
    assert r5.rows[0].beta == pytest.approx(0.7775, abs=1e-4)


def test_two_sigma_shift_n5_hand_calculated():
    # β = Φ(3 - 2√5) - Φ(-3 - 2√5) = Φ(-1.472) - Φ(-7.472) ≈ 0.0705, calculado a mano.
    assert float(xbar_beta(2.0, 5)) == pytest.approx(0.0705, abs=5e-4)


def test_oc_is_symmetric_and_signal_probability_is_complement():
    for d in (0.3, 1.0, 2.5):
        assert float(xbar_beta(d, 4)) == pytest.approx(float(xbar_beta(-d, 4)))
        assert float(xbar_beta(d, 4)) + float(xbar_signal_probability(d, 4)) == pytest.approx(1.0)


def test_ats_units_and_sampling_load():
    r = compute_arl("xbar", n=4, sampling_interval=0.5, shifts=[1.5])
    row = r.rows[0]
    assert r.ats0 == pytest.approx(r.arl0 * 0.5)
    assert row.ats1 == pytest.approx(row.arl1 * 0.5)
    assert row.units_to_detect == pytest.approx(row.arl1 * 4)
    assert r.sampling_load == pytest.approx(8.0)
    ind = compute_arl("individuals", n=7, sampling_interval=2.0)
    assert ind.sampling_load == pytest.approx(0.5)  # n se ignora en individuales


def test_curves_shapes():
    r = compute_arl("xbar", n=5)
    assert r.oc_curve[0].x == 0.0 and r.oc_curve[0].y == pytest.approx(1 - r.alpha)
    ys = [p.y for p in r.oc_curve]
    assert all(a >= b for a, b in zip(ys, ys[1:]))  # β decrece con δ
    assert r.arl_curve[0].y == pytest.approx(r.arl0)


def test_p_chart_oc_montgomery_ch7():
    m = p_chart_model(0.20, 50)
    assert m.ucl == pytest.approx(0.3697, abs=1e-4)
    assert m.lcl == pytest.approx(0.0303, abs=1e-4)
    assert design._count_bounds(m) == (2, 18)
    for p in (0.05, 0.20, 0.35, 0.45):
        expected = stats.binom.cdf(18, 50, p) - stats.binom.cdf(1, 50, p)
        assert float(count_chart_beta(m, p)) == pytest.approx(expected)
    r = compute_arl("p", n=50, p0=0.20, p1=[0.30])
    alpha = 1 - (stats.binom.cdf(18, 50, 0.2) - stats.binom.cdf(1, 50, 0.2))
    assert r.alpha == pytest.approx(alpha)
    assert r.arl0 == pytest.approx(1 / alpha)
    assert r.arl0 != pytest.approx(370.4, abs=0.1)  # discreto: no es el nominal
    assert r.rows[0].units_to_detect == pytest.approx(r.rows[0].arl1 * 50)


def test_c_chart_oc_montgomery_example_7_3():
    m = c_chart_model(19.85)
    assert m.ucl == pytest.approx(33.22, abs=0.01)
    assert m.lcl == pytest.approx(6.48, abs=0.01)
    assert design._count_bounds(m) == (7, 33)
    for c in (10.0, 19.85, 30.0):
        expected = stats.poisson.cdf(33, c) - stats.poisson.cdf(6, c)
        assert float(count_chart_beta(m, c)) == pytest.approx(expected)


def test_discrete_arl0_is_explained():
    r = compute_arl("c", c0=4.0, c1=[8.0])
    # LCS = 4 + 3·2 = 10 -> sin señal si x <= 10; LCI = -2 -> 0 (truncado).
    alpha = stats.poisson.sf(10, 4.0)
    assert r.alpha == pytest.approx(alpha)
    text = " ".join(r.interpretation.findings)
    assert "370.4" in text and "discreto" in text and "truncado" in text


def test_degenerate_design_raises():
    with pytest.raises(ValueError):
        compute_arl("p", n=1, p0=0.5)  # LCS >= 1 y LCI <= 0: nunca da señal
    with pytest.raises(ValueError):
        compute_arl("p", n=50)  # falta p0
    with pytest.raises(ValueError):
        compute_arl("p", n=50, p0=0.1, p1=[1.2])


# --------------------------------------------------------------- simulación


def test_simulation_matches_exact_within_three_standard_errors():
    for chart, n in (("individuals", 1), ("xbar", 5)):
        exact = compute_arl(chart, n=n)
        sim = compute_arl(chart, n=n, force_simulation=True)
        assert sim.method == "simulation" and sim.alpha is None
        assert any("error estándar" in f for f in sim.interpretation.findings)
        for e_row, s_row in zip(exact.rows, sim.rows):
            assert s_row.beta is None and s_row.std_error >= 0
            # Con δ = 3 y n = 5 casi todas las corridas duran 1 muestra (SE ≈ 0):
            # se admite además una diferencia de 0.2 %.
            assert abs(s_row.arl1 - e_row.arl1) <= max(3 * s_row.std_error, 0.002 * e_row.arl1)
        # ARL0: error estándar de una geométrica ≈ √(ARL0(ARL0 - 1)/R).
        se = math.sqrt(exact.arl0 * (exact.arl0 - 1) / 5000)
        assert abs(sim.arl0 - exact.arl0) <= 3 * se


def _markov_arl_we1_we4(shift, L=3.0, run=8):
    """ARL exacto de WE1 + WE4 (8 seguidos del mismo lado) por cadena de Markov.

    Estados transitorios: inicio, k puntos seguidos arriba (k = 1..7) y abajo.
    Calculado aquí para validar la simulación; no es un valor publicado.
    """
    up = stats.norm.cdf(L - shift) - stats.norm.cdf(-shift)
    dn = stats.norm.cdf(-shift) - stats.norm.cdf(-L - shift)
    k = run - 1
    size = 1 + 2 * k  # 0 = inicio, 1..k arriba, k+1..2k abajo
    Q = np.zeros((size, size))

    def a(i):
        return i

    def b(i):
        return k + i

    for s in range(size):
        if s == 0 or s > k:  # inicio o abajo: subir abre racha arriba
            Q[s, a(1)] += up
        else:
            if s < k:
                Q[s, a(s + 1)] += up
        if s == 0 or s <= k:
            Q[s, b(1)] += dn
        else:
            i = s - k
            if i < k:
                Q[s, b(i + 1)] += dn
    arl = np.linalg.solve(np.eye(size) - Q, np.ones(size))
    return float(arl[0])


def test_simulation_with_we4_matches_markov_chain():
    r = compute_arl("individuals", rules=["WE1", "WE4"], shifts=[0.5, 1.0])
    assert r.method == "simulation"
    exact0 = _markov_arl_we1_we4(0.0)
    for row in r.rows:
        assert abs(row.arl1 - _markov_arl_we1_we4(row.shift)) <= 3 * row.std_error
    # ARL0 como fila con δ = 0, para disponer de su error estándar.
    sim0 = compute_arl("individuals", rules=["WE1", "WE4"], shifts=[0.0])
    assert abs(sim0.rows[0].arl1 - exact0) <= 3 * sim0.rows[0].std_error


def test_simulation_is_reproducible_and_fast():
    rules = ["WE1", "WE2", "WE3", "WE4", "N2", "N3", "N4", "N5", "N6", "N7", "N8"]
    t0 = time.perf_counter()
    a = compute_arl("xbar", n=5, rules=rules)
    elapsed = time.perf_counter() - t0
    b = compute_arl("xbar", n=5, rules=rules)
    assert a.arl0 == b.arl0 and [r.arl1 for r in a.rows] == [r.arl1 for r in b.rows]
    assert elapsed < 5.0
    # Las reglas suplementarias aumentan las falsas alarmas.
    assert a.arl0 < 370.4 / 2
    assert any("multiplican las falsas alarmas" in f for f in a.interpretation.findings)


def test_simulation_detector_is_injectable():
    calls = []

    def make(model, rules):
        def detect(x):
            calls.append(x.shape)
            return np.abs(x - model.center) > model.limit_width * model.sigma

        return detect

    r = compute_arl("individuals", shifts=[2.0], rules=["WE1"], force_simulation=True,
                    detector=make, max_runs=500)
    assert calls
    exact = 1 / float(xbar_signal_probability(2.0, 1))
    assert abs(r.rows[0].arl1 - exact) <= 3 * r.rows[0].std_error


def test_zone_rules_skipped_on_truncated_attribute_chart():
    r = compute_arl("c", c0=4.0, c1=[8.0], rules=["WE1", "WE2", "WE4"], max_runs=1000)
    assert r.method == "simulation"
    assert any("WE2" in w and "zonas" in w for w in r.interpretation.warnings)


def test_budget_censoring_is_reported():
    r = compute_arl("xbar", n=5, rules=["N7"], shifts=[3.0], max_runs=200, max_length=500)
    assert any("cotas inferiores" in w for w in r.interpretation.warnings)
    ArlResponse.model_validate(asdict(r))


# --------------------------------------------------------------- contrato


def test_arl_results_convert_to_contract():
    for kwargs in (
        {"chart": "xbar", "n": 5},
        {"chart": "individuals", "rules": ["WE1", "WE2"], "max_runs": 500},
        {"chart": "p", "n": 100, "p0": 0.05},
        {"chart": "c", "c0": 20.0, "c1": [25.0, 30.0]},
    ):
        r = compute_arl(**kwargs)
        model = ArlResponse.model_validate(asdict(r))
        assert model.interpretation.summary


def test_compare_designs_table():
    res = compare_designs([1, 5], limit_widths=[2.5, 3.0], sampling_intervals=[0.2, 1.0], shift=1.0)
    assert len(res.rows) == 8
    row = next(r for r in res.rows if r.n == 5 and r.limit_width == 3.0 and r.sampling_interval == 1.0)
    assert row.arl0 == pytest.approx(370.4, abs=0.05)
    assert row.arl1 == pytest.approx(4.5, abs=0.01)
    assert row.sampling_load == pytest.approx(5.0)
    same_load = [r for r in res.rows if r.sampling_load == pytest.approx(5.0)]
    assert len(same_load) == 4  # n = 5 cada hora y n = 1 cada 0.2 h, con dos L
    model = CompareResponse.model_validate(asdict(res))
    assert "más rápido" in model.interpretation.summary
    assert any("misma carga" in f for f in model.interpretation.findings)
