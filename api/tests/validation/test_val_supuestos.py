"""Validación independiente de assumptions.py.

- ACF por FFT y Ljung-Box escrito de nuevo (no producto punto por rezago).
- Prueba de rachas: distribución exacta por enumeración de todas las disposiciones.
- Anderson-Darling: estadístico con `scipy.special.ndtr` y tamaño real del
  contraste por simulación bajo H0.

Las pruebas marcadas `xfail(strict=True)` documentan hallazgos: fallan hoy y
pasarán a XPASS (y harán fallar la corrida) cuando se corrija el código, para
que se quite la marca.
"""

import math
import warnings

import numpy as np
import pytest
from scipy import stats

from app.spc.assumptions import (
    _runs_pmf,
    acf,
    anderson_darling_critical_value,
    anderson_darling_statistic,
    autocorrelation,
    ljung_box_test,
    runs_test,
    shapiro_wilk_test,
)

from .independiente import (
    acf_por_fft,
    ad_estadistico_propio,
    ad_tamano_real,
    ljung_box_propio,
    rachas_por_enumeracion,
    rachas_valor_p_exacto,
)


def test_acf_y_ljung_box_por_otro_camino():
    rng = np.random.default_rng(4)
    for _ in range(100):
        n = int(rng.integers(8, 300))
        y = np.cumsum(rng.normal(size=n)) * rng.uniform(0, 1) + rng.normal(size=n)
        m = int(rng.integers(1, min(30, n - 1)))
        assert acf(y, m) == pytest.approx(acf_por_fft(y, m), abs=1e-12)
        q, p = ljung_box_propio(y, m)
        t = ljung_box_test(y, m)
        assert t.statistic == pytest.approx(q, rel=1e-12)
        assert t.p_value == pytest.approx(p, abs=1e-12)


def test_banda_acf():
    y = np.random.default_rng(1).normal(size=150)
    ac = autocorrelation(y, alpha=0.05)
    assert ac.band == pytest.approx(stats.norm.isf(0.025) / math.sqrt(150))
    assert ac.significant_lags == [k for k, v in zip(ac.lags, ac.values) if abs(v) > ac.band]


@pytest.mark.parametrize("n1, n2", [(1, 1), (2, 5), (5, 5), (4, 7), (8, 8), (3, 9)])
def test_distribucion_exacta_de_rachas(n1, n2):
    a, b = _runs_pmf(n1, n2), rachas_por_enumeracion(n1, n2)
    assert set(a) == set(b)
    for r in a:
        assert a[r] == pytest.approx(b[r], abs=1e-15)


def test_valor_p_exacto_de_rachas():
    x = [3, 5, 1, 8, 9, 7, 2, 4, 6, 10, 11, 12, 0.5, 13, 14, 15]
    med = float(np.median(x))
    s = [v > med for v in x if v != med]
    R = 1 + sum(1 for a, b in zip(s, s[1:]) if a != b)
    pmf = rachas_por_enumeracion(sum(s), len(s) - sum(s))
    p = min(1, 2 * min(sum(v for r, v in pmf.items() if r <= R), sum(v for r, v in pmf.items() if r >= R)))
    assert runs_test(x).p_value == pytest.approx(p)


def _serie_con_rachas(n1, R):
    """Serie de 2·n1 valores (n1 arriba y n1 abajo de la mediana 0) con exactamente R rachas (R par)."""
    k = R // 2  # rachas de cada tipo
    sizes = [n1 - k + 1] + [1] * (k - 1)
    seq, u, d = [], 0, 0
    for a in sizes:
        seq += [10.0 + 0.01 * (u + i) for i in range(a)]
        u += a
        seq += [-10.0 - 0.01 * (d + i) for i in range(a)]
        d += a
    return seq


def test_rachas_aproximacion_normal_por_encima_de_60():
    x = _serie_con_rachas(31, 24)
    pmf = _runs_pmf(31, 31)
    exact = min(1, 2 * min(sum(v for r, v in pmf.items() if r <= 24), sum(v for r, v in pmf.items() if r >= 24)))
    t = runs_test(x)
    assert "24 rachas" in t.conclusion
    assert t.p_value == pytest.approx(exact, rel=0.05)  # exacto 0.0541; software 0.0405 (rechaza)


@pytest.mark.parametrize("n1, n2, z", [(501, 500, -2.0), (600, 700, 2.0), (1500, 1500, -3.0), (2500, 2400, 6.0)])
def test_rachas_log_gamma_frente_a_aritmetica_exacta(n1, n2, z):
    """H10, corregido: por encima de 1 000 datos `_runs_pmf` usa log-gamma. Frente a la
    suma con fracciones de enteros grandes, el error relativo del valor p es < 1e-10
    (medido: ≤ 5e-12 hasta n = 4 900, también en z = ±6)."""
    m = n1 + n2
    E = 2 * n1 * n2 / m + 1
    sd = math.sqrt(2 * n1 * n2 * (2 * n1 * n2 - m) / (m * m * (m - 1)))
    r = int(round(E + z * sd))
    pmf = _runs_pmf(n1, n2)
    p_sw = min(1.0, 2 * min(sum(v for k, v in pmf.items() if k <= r), sum(v for k, v in pmf.items() if k >= r)))
    assert p_sw == pytest.approx(rachas_valor_p_exacto(n1, n2, r), rel=1e-10)


def test_ad_estadistico_por_otro_camino():
    for seed in range(5):
        x = np.random.default_rng(seed).normal(size=30 + 20 * seed)
        assert anderson_darling_statistic(x) == pytest.approx(ad_estadistico_propio(x), rel=1e-12)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert anderson_darling_statistic(x) == pytest.approx(stats.anderson(x, "norm").statistic, rel=1e-12)


def test_ad_tamano_real_n15():
    c, _ = anderson_darling_critical_value(15, 0.05)
    assert 0.045 <= ad_tamano_real(15, c, reps=40_000) <= 0.055


@pytest.mark.parametrize("n, alpha", [(5, 0.05), (8, 0.05), (30, 0.10), (100, 0.05), (200, 0.01), (30, 0.02)])
def test_ad_tamano_real_tras_la_correccion(n, alpha):
    """H3, corregido: con la tabla de D'Agostino y Stephens (1986) el tamaño real queda a
    ±0.003 del nominal para n de 5 a 200 (100 000 réplicas por caso en docs/validacion.md),
    también con α interpolado (0.02)."""
    c, _ = anderson_darling_critical_value(n, alpha)
    real = ad_tamano_real(n, c, reps=40_000, seed=11 + n)
    se = math.sqrt(alpha * (1 - alpha) / 40_000)
    assert abs(real - alpha) < max(4 * se, 0.1 * alpha)


def test_ad_n3_no_puede_rechazar():
    """Observación (solo por la librería; la API exige n >= 8): con n = 3 el máximo de A² es
    0.4878, menor que el crítico de α = 0.05 (0.5013): la prueba no puede rechazar nunca."""
    best = max(anderson_darling_statistic([0.0, t, 1.0]) for t in np.linspace(0.0005, 0.9995, 2000))
    assert best == pytest.approx(0.4878, abs=1e-3)
    assert best < anderson_darling_critical_value(3, 0.05)[0]


def test_ad_tabla_dagostino_1986_si_da_el_tamano_nominal():
    """Valor correcto propuesto: 0.752/(1 + 0.75/n + 2.25/n²) (la que usa scipy 1.18)."""
    for n in (8, 15, 30):
        c = 0.752 / (1 + 0.75 / n + 2.25 / n**2)
        assert 0.045 <= ad_tamano_real(n, c, reps=40_000) <= 0.056


def test_ad_n3_valor_critico_positivo():
    assert anderson_darling_critical_value(3, 0.05)[0] > 0


def test_shapiro_igual_a_scipy():
    x = np.random.default_rng(2).normal(size=25)
    assert shapiro_wilk_test(x).p_value == pytest.approx(stats.shapiro(x).pvalue)
