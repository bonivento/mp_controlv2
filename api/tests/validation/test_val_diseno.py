"""Validación independiente de design.py (ARL, ATS, OC).

- Fórmulas exactas recalculadas con sumas propias (binomial y Poisson a mano).
- Simulación del software frente a la cadena de Markov propia de WE1-WE4
  (Champ y Woodall, 1987); la cadena da ARL0 = 91.75.
"""

import math

import numpy as np
import pytest
from scipy import stats

from app.spc.design import compare_designs, compute_arl

from .independiente import arl_western_electric


def test_arl_exacto_xbar_a_mano():
    for n, L, d in ((1, 3.0, 1.0), (5, 3.0, 1.0), (4, 2.5, 0.75), (9, 3.2, 0.5)):
        r = compute_arl("xbar", n=n, limit_width=L, shifts=[d], sampling_interval=0.5)
        a = 2 * (1 - stats.norm.cdf(L))
        beta = stats.norm.cdf(L - d * math.sqrt(n)) - stats.norm.cdf(-L - d * math.sqrt(n))
        assert r.alpha == pytest.approx(a, rel=1e-10)
        assert r.arl0 == pytest.approx(1 / a, rel=1e-10)
        assert r.ats0 == pytest.approx(0.5 / a, rel=1e-10)
        assert r.rows[0].beta == pytest.approx(beta, rel=1e-10)
        assert r.rows[0].arl1 == pytest.approx(1 / (1 - beta), rel=1e-10)
        assert r.rows[0].units_to_detect == pytest.approx(n / (1 - beta), rel=1e-10)
        assert r.sampling_load == pytest.approx(n / 0.5)


def _binom_cdf(k, n, p):
    return sum(math.comb(n, j) * p**j * (1 - p) ** (n - j) for j in range(0, k + 1)) if k >= 0 else 0.0


def _pois_cdf(k, lam):
    return sum(math.exp(-lam) * lam**j / math.factorial(j) for j in range(0, k + 1)) if k >= 0 else 0.0


def test_arl0_real_de_graficos_discretos():
    # p, n = 50, p0 = 0.2: LCS = 0.3697 -> D <= 18; LCI = 0.0303 -> D >= 2
    r = compute_arl("p", n=50, p0=0.2, p1=[0.3])
    alpha = 1 - (_binom_cdf(18, 50, 0.2) - _binom_cdf(1, 50, 0.2))
    assert r.alpha == pytest.approx(alpha, rel=1e-9)
    assert r.arl0 == pytest.approx(1 / alpha, rel=1e-9)
    b1 = _binom_cdf(18, 50, 0.3) - _binom_cdf(1, 50, 0.3)
    assert r.rows[0].arl1 == pytest.approx(1 / (1 - b1), rel=1e-9)
    # c, c0 = 19.85: LCS = 33.22 -> x <= 33; LCI = 6.48 -> x >= 7
    r = compute_arl("c", c0=19.85, c1=[25.0])
    alpha = 1 - (_pois_cdf(33, 19.85) - _pois_cdf(6, 19.85))
    assert r.arl0 == pytest.approx(1 / alpha, rel=1e-9)
    # c con límite entero exacto: c0 = 4 -> LCS = 10; x = 10 no es señal
    r = compute_arl("c", c0=4.0, c1=[8.0])
    assert r.alpha == pytest.approx(1 - _pois_cdf(10, 4.0), rel=1e-9)


def test_simulacion_igual_a_cadena_de_markov_we1_a_we4():
    rules = ["WE1", "WE2", "WE3", "WE4"]
    assert arl_western_electric(0.0) == pytest.approx(91.75, abs=0.01)
    r = compute_arl("individuals", rules=rules, shifts=[0.5, 1.0, 2.0], max_runs=8000, seed=7)
    assert abs(r.arl0 - arl_western_electric(0.0)) < 4 * r.arl0_std_error
    for row in r.rows:
        assert abs(row.arl1 - arl_western_electric(row.shift)) < 4 * row.std_error
    # X-barra con n = 4 y δ = 0.5σ equivale a δ = 1 en unidades de σ/√n
    r = compute_arl("xbar", n=4, rules=rules, shifts=[0.5], max_runs=8000, seed=8)
    assert abs(r.rows[0].arl1 - arl_western_electric(1.0)) < 4 * r.rows[0].std_error


def test_simulacion_igual_a_exacto_en_atributos():
    for kw in ({"chart": "p", "n": 50, "p0": 0.2, "p1": [0.3]}, {"chart": "c", "c0": 19.85, "c1": [25.0]}):
        ex = compute_arl(**kw)
        sim = compute_arl(**kw, force_simulation=True, max_runs=6000)
        assert abs(sim.arl0 - ex.arl0) < 4 * sim.arl0_std_error
        assert abs(sim.rows[0].arl1 - ex.rows[0].arl1) < 4 * sim.rows[0].std_error


def test_comparacion_de_disenos_a_mano():
    res = compare_designs([2, 8], limit_widths=[3.0], sampling_intervals=[0.25, 1.0], shift=1.0)
    for row in res.rows:
        a = 2 * stats.norm.sf(3.0)
        p1 = stats.norm.sf(3 - math.sqrt(row.n)) + stats.norm.cdf(-3 - math.sqrt(row.n))
        assert row.arl0 == pytest.approx(1 / a)
        assert row.ats1 == pytest.approx(row.sampling_interval / p1)
        assert row.sampling_load == pytest.approx(row.n / row.sampling_interval)


# ---------------------------------------------------------------- segunda pasada


def test_we4_en_c_truncado_el_arl0_simulado_ya_incluye_la_asimetria():
    """Duda 4 de los autores: design.py aplica WE4 en p y c truncados sin advertir. La
    simulación usa la distribución discreta real, así que el ARL0 informado ya es el real
    (con asimetría y empates): coincide con la cadena propia de WE1 + WE4. c0 = 4 (LC
    entera, empates en 4): ARL0 = 1/(...) de la cadena = 264."""
    from .independiente import arl_racha
    lam = 4.0
    p_out = stats.poisson.sf(10, lam)                       # LCS = 10: X >= 11 señala
    p_up = stats.poisson.cdf(10, lam) - stats.poisson.cdf(4, lam)
    p_dn = stats.poisson.cdf(3, lam)
    exacto = arl_racha(p_up, p_dn, 8, p_out)
    r = compute_arl("c", c0=lam, c1=[8.0], rules=["WE1", "WE4"], max_runs=4000, seed=11)
    assert abs(r.arl0 - exacto) < 4 * r.arl0_std_error


def test_diseno_con_we4_puede_senalar_mejoras():
    r = compute_arl("c", c0=4.0, c1=[2.0], rules=["WE1", "WE4"], max_runs=1500, seed=3)
    assert r.rows[0].arl1 < 40
    assert not any("no puede señalar mejoras" in f for f in r.interpretation.findings)


def test_concordancia_carga_unitaria():
    r = compute_arl("c", c0=4.0, c1=[8.0])
    assert not any("1 unidades" in f for f in r.interpretation.findings)
