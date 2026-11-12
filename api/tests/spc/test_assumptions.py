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


def test_anderson_darling_critical_value_dagostino_stephens_table():
    # D'Agostino y Stephens (1986), tabla 4.7: 0.752 / (1 + 0.75/n + 2.25/n²)
    # para α = 0.05. Antes se usaba Stephens (1974), 0.787 / (1 + 4/n - 25/n²),
    # cuyo tamaño real era 0.038 a 0.061 y que con n = 3 daba un crítico negativo
    # (hallazgo H3 del validador); esta es la tabla de scipy.stats.anderson.
    n = 50
    expected = 0.752 / (1 + 0.75 / n + 2.25 / n**2)
    value, in_table = anderson_darling_critical_value(n, 0.05)
    assert value == pytest.approx(expected)
    assert in_table
    # α fuera de la tabla: se usa el extremo y se avisa.
    v, ok = anderson_darling_critical_value(n, 0.001)
    assert not ok and v == pytest.approx(1.035 / (1 + 0.75 / n + 2.25 / n**2))
    # Mismos críticos que scipy (redondeados a 3 decimales por scipy).
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ref = stats.anderson(np.random.default_rng(0).normal(size=n), "norm").critical_values
    ours = [anderson_darling_critical_value(n, a)[0] for a in (0.15, 0.10, 0.05, 0.025, 0.01)]
    assert ours == pytest.approx(list(ref), abs=5e-4)
    # El factor es positivo para cualquier n: el crítico nunca es negativo.
    assert all(anderson_darling_critical_value(k, 0.05)[0] > 0 for k in range(1, 10))


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


def test_runs_test_is_exact_for_large_samples():
    """Con n1 + n2 > 60 también se usa la distribución exacta (hallazgo H10).

    Serie de 62 datos (31 arriba y 31 abajo de la mediana) con 24 rachas: el
    valor p exacto es 2·P(R <= 24) con la distribución de Wald-Wolfowitz.
    La aproximación normal sin corrección daba 0.0405 y rechazaba.
    """
    up = [10.0 + 0.01 * i for i in range(31)]
    down = [-10.0 - 0.01 * i for i in range(31)]
    # 12 rachas de cada lado: tamaños 20, 1, ..., 1
    sizes = [20] + [1] * 11
    x, u, d = [], 0, 0
    for a in sizes:
        x += up[u:u + a]
        u += a
        x += down[d:d + a]
        d += a
    t = runs_test(x)
    pmf = _runs_pmf(31, 31)
    exact = 2 * sum(v for r, v in pmf.items() if r <= 24)
    assert "24 rachas" in t.conclusion and "exacto" in t.conclusion
    assert t.p_value == pytest.approx(exact)
    assert not t.reject  # exacto ≈ 0.054 > 0.05


def test_runs_pmf_large_n_matches_integer_formula():
    """Por encima de 1000 datos la distribución se calcula con log-gamma; en
    n1 + n2 = 960 se compara la vía de log-gamma con la de enteros exactos."""
    from app.spc import assumptions as A

    exact = A._runs_pmf(400, 560)
    old = A._EXACT_INTEGER_LIMIT
    try:
        A._EXACT_INTEGER_LIMIT = 0
        approx = A._runs_pmf(400, 560)
    finally:
        A._EXACT_INTEGER_LIMIT = old
    for r, p in exact.items():
        assert approx[r] == pytest.approx(p, rel=1e-9, abs=1e-300)
    big = A._runs_pmf(3000, 3000)
    assert sum(big.values()) == pytest.approx(1.0, abs=1e-9)


def test_interpretation_does_not_claim_assumptions_hold():
    res = analyze_assumptions([10.1, 9.8, 10.3, 10.0, 9.7, 10.2, 9.9, 10.4])
    s = res.interpretation.summary
    assert "no hay evidencia en contra" in s and "n = 8" in s and "poca potencia" in s
    assert "se cumplen" not in s


def test_interpretation_mentions_instability_when_normality_is_rejected():
    rng = np.random.default_rng(7)
    x = np.concatenate([rng.normal(0, 1, 60), rng.normal(4, 1, 60)])  # desplazamiento de la media
    res = analyze_assumptions(x)
    assert not res.is_normal
    assert any("en control" in w and "Box-Cox" in w for w in res.interpretation.warnings)


# ------------------------------------------------------ tercera ronda (H21, H25)


def test_anderson_darling_cannot_reject_with_three_points():
    """Con n = 3 el máximo de A² es 0.48777 (dos valores iguales y uno distinto),
    menor que el crítico 0.752/1.5 = 0.5013 de α = 0.05."""
    assert anderson_darling_statistic([0.0, 0.0, 1.0]) < 0.48777 + 1e-9
    crit, _ = anderson_darling_critical_value(3, 0.05)
    assert crit == pytest.approx(0.752 / 1.5)
    r = anderson_darling_test([1.0, 2.0, 3.5])
    assert "no puede rechazar" in r.conclusion and "casi no tiene potencia" not in r.conclusion
    # Con α = 0.15 el crítico (0.374) sí es alcanzable: no se dice que no pueda rechazar.
    assert "no puede rechazar" not in anderson_darling_test([1.0, 2.0, 3.5], alpha=0.15).conclusion


def test_shape_is_compared_with_its_standard_error():
    """H21. EE(G2) con n = 8: EE(G1) = √(6·8·7/(6·9·11)) = 0.7521 y
    EE(G2) = √(4·63·0.5657/(5·13)) = 1.481 (Joanes y Gill, 1998)."""
    from app.spc.interpretation import _shape_standard_errors
    se1, se2 = _shape_standard_errors(8)
    assert se1 == pytest.approx(math.sqrt(6 * 8 * 7 / (6 * 9 * 11)))
    assert se2 == pytest.approx(1.481, abs=1e-3)
    it = analyze_assumptions([10.1, 9.8, 10.3, 10.0, 9.7, 10.2, 9.9, 10.4]).interpretation
    assert not any(f.startswith("Forma de la distribución") for f in it.findings)
    assert any("a menos de 1,96 errores estándar" in f for f in it.findings)
    # Datos claramente asimétricos con n = 200: sí se describe la forma.
    x = np.random.default_rng(1).exponential(size=200)
    assert any(f.startswith("Forma de la distribución") for f in analyze_assumptions(x).interpretation.findings)


def test_shape_false_claims_near_nominal_with_normal_data():
    """H21: con datos normales el hallazgo de forma aparecía en el 75 % de las muestras
    de n = 8; comparando con 1.96·EE debe quedar cerca o por debajo del 5 % por índice."""
    rng = np.random.default_rng(7)
    hits = 0
    for _ in range(300):
        it = analyze_assumptions(rng.normal(size=20)).interpretation
        hits += any(f.startswith("Forma de la distribución") for f in it.findings)
    assert hits / 300 < 0.12


def test_expected_lags_out_of_band_matches_simulation():
    """H23: el número esperado de rezagos fuera de ±1.96/√n con datos i.i.d. Por
    simulación propia (20 000 series, n = 120, m = 20) es 0.775; la aproximación con
    Var(r_k) = (n - k)/(n(n + 2)) da 0.788. 1 - 0.95^20 = 0.64 no se cita."""
    from app.spc.interpretation import _acf_chance
    n, m = 120, 20
    exp, _ = _acf_chance(n, list(range(1, m + 1)), 1.959964 / math.sqrt(n))
    rng = np.random.default_rng(0)
    x = rng.standard_normal((4000, n))
    x -= x.mean(axis=1, keepdims=True)
    den = (x * x).sum(axis=1)
    cnt = sum((np.abs((x[:, :-k] * x[:, k:]).sum(axis=1) / den) > 1.959964 / math.sqrt(n)).mean()
              for k in range(1, m + 1))
    assert exp == pytest.approx(cnt, abs=0.06)
