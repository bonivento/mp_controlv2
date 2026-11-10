"""Pruebas de normalidad e independencia."""

import math
import warnings
from dataclasses import asdict

import numpy as np
import pytest
from scipy import stats

from app.schemas.assumptions import AssumptionsResponse
from app.spc.assumptions import (
    _runs_pmf,
    acf,
    analyze_assumptions,
    anderson_darling_critical_value,
    anderson_darling_statistic,
    anderson_darling_test,
    autocorrelation,
    default_max_lag,
    ljung_box_test,
    qq_points,
    runs_test,
    shapiro_wilk_test,
)


def _ar1(phi, n, seed):
    rng = np.random.default_rng(seed)
    e = rng.normal(size=n)
    x = np.zeros(n)
    for t in range(1, n):
        x[t] = phi * x[t - 1] + e[t]
    return x


# ---------------------------------------------------------------- normalidad


def test_shapiro_matches_scipy_and_states_h0():
    x = np.random.default_rng(1).normal(10, 2, 40)
    t = shapiro_wilk_test(x)
    w, p = stats.shapiro(x)
    assert t.statistic == pytest.approx(w) and t.p_value == pytest.approx(p)
    assert t.null_hypothesis.startswith("Los datos provienen de una distribución normal")
    assert "W =" in t.conclusion


def test_anderson_darling_statistic_matches_scipy():
    x = np.random.default_rng(2).normal(size=60)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ref = stats.anderson(x, "norm").statistic
    assert anderson_darling_statistic(x) == pytest.approx(ref, rel=1e-10)


def test_anderson_darling_critical_value_stephens_table():
    # Stephens (1974), caso 3: 0.787 / (1 + 4/n - 25/n²) para α = 0.05.
    n = 50
    expected = 0.787 / (1 + 4 / n - 25 / n**2)
    value, in_table = anderson_darling_critical_value(n, 0.05)
    assert value == pytest.approx(expected)
    assert in_table
    # α fuera de la tabla: se usa el extremo y se avisa.
    v, ok = anderson_darling_critical_value(n, 0.001)
    assert not ok and v == pytest.approx(1.092 / (1 + 4 / n - 25 / n**2))


def test_anderson_darling_has_no_p_value_and_detects_skew():
    expo = np.random.default_rng(3).exponential(size=200)
    t = anderson_darling_test(expo)
    assert t.p_value is None and t.critical_value is not None
    assert t.reject
    normal = np.random.default_rng(4).normal(size=200)
    assert not anderson_darling_test(normal).reject


def test_qq_plotting_positions():
    # Montgomery, cap. 3 (gráfico de probabilidad normal): posiciones (j - 0.5)/n.
    pts = qq_points([4.0, 1.0, 3.0, 2.0])
    assert [p.observed for p in pts] == [1.0, 2.0, 3.0, 4.0]
    expected = stats.norm.ppf([0.125, 0.375, 0.625, 0.875])
    assert [p.theoretical for p in pts] == pytest.approx(list(expected))


# ------------------------------------------------------------- independencia


def test_acf_hand_calculated():
    # x = 1..5: desvíos -2, -1, 0, 1, 2; Σd² = 10.
    # r1 = [(-2)(-1) + (-1)(0) + (0)(1) + (1)(2)]/10 = 0.4
    # r2 = [(-2)(0) + (-1)(1) + (0)(2)]/10 = -0.1
    r = acf([1, 2, 3, 4, 5], 2)
    assert r == pytest.approx([0.4, -0.1])


def test_ljung_box_hand_calculated():
    # Q = n(n+2) Σ r_k²/(n-k) = 5·7·(0.16/4 + 0.01/3) con los r de la prueba anterior.
    t = ljung_box_test([1, 2, 3, 4, 5], max_lag=2)
    q = 35 * (0.16 / 4 + 0.01 / 3)
    assert t.statistic == pytest.approx(q)
    assert t.p_value == pytest.approx(stats.chi2.sf(q, 2))


def test_default_max_lag_rule():
    assert default_max_lag(200) == 20
    assert default_max_lag(40) == 10
    assert default_max_lag(8) == 2


def test_band_and_significant_lags_on_ar1():
    x = _ar1(0.8, 200, seed=11)
    ac = autocorrelation(x)
    assert ac.band == pytest.approx(1.959964 / math.sqrt(200), rel=1e-5)
    assert 1 in ac.significant_lags
    assert ac.values[0] > 0.6
    assert ljung_box_test(x).reject
    runs = runs_test(x)
    assert runs.reject and "menos rachas" in runs.conclusion


def test_runs_test_exact_small_sample():
    # x = 1..10, mediana 5.5: - - - - - + + + + + -> R = 2 con n1 = n2 = 5.
    # P(R = 2) = 2 / C(10, 5) = 2/252; p bilateral = 2·P(R <= 2) = 4/252.
    t = runs_test(list(range(1, 11)))
    assert t.p_value == pytest.approx(4 / 252)
    assert t.reject
    # Alternancia perfecta: R = 10, P(R = 10) = 2/252 -> p = 4/252.
    alt = runs_test([1, 10, 2, 9, 3, 8, 4, 7, 5, 6])
    assert alt.p_value == pytest.approx(4 / 252)
    assert alt.reject and "más rachas" in alt.conclusion


def test_runs_pmf_is_a_distribution_with_known_mean():
    n1, n2 = 7, 9
    pmf = _runs_pmf(n1, n2)
    assert sum(pmf.values()) == pytest.approx(1.0)
    mean = sum(r * p for r, p in pmf.items())
    assert mean == pytest.approx(2 * n1 * n2 / (n1 + n2) + 1)


def test_runs_test_drops_median_ties_and_handles_one_side():
    t = runs_test([1, 5, 5, 5, 5, 5, 5, 9])
    assert t.p_value is None or t.p_value <= 1
    flat_side = runs_test([5, 5, 5, 5, 5, 6, 7, 8])  # mediana 5: abajo no queda nada
    assert flat_side.p_value is None and not flat_side.reject


# ---------------------------------------------------------- análisis completo


def test_white_noise_passes_everything_and_converts_to_contract():
    x = np.random.default_rng(21).normal(100, 5, 80)
    res = analyze_assumptions(x)
    assert res.is_normal and res.is_independent
    assert [t.name for t in res.normality] == ["Shapiro-Wilk", "Anderson-Darling"]
    assert [t.name for t in res.independence] == ["Ljung-Box", "Rachas"]
    model = AssumptionsResponse.model_validate(asdict(res))
    assert model.normality[1].p_value is None
    assert "compatibles" in model.interpretation.summary


def test_non_normal_and_dependent_flags():
    expo = np.random.default_rng(5).exponential(size=150)
    res = analyze_assumptions(expo)
    assert not res.is_normal
    assert any("capacidad" in w for w in res.interpretation.warnings)
    dep = analyze_assumptions(_ar1(0.85, 150, seed=9))
    assert not dep.is_independent
    assert any("AR(1)" in w for w in dep.interpretation.warnings)


def test_constant_data_is_rejected():
    with pytest.raises(ValueError):
        analyze_assumptions([3.0] * 10)
