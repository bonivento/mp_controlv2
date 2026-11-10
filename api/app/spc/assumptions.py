"""Validación de supuestos: normalidad e independencia.

Los gráficos de Shewhart y los índices de capacidad suponen observaciones
normales e independientes (Montgomery, *Introduction to Statistical Quality
Control*, cap. 5 "Methods and Philosophy of SPC" y cap. 8 "Process and
Measurement System Capability Analysis"). Este módulo pone a prueba ambos
supuestos y deja escrita la conclusión.

Pruebas implementadas (numpy y scipy, sin statsmodels):

- Shapiro-Wilk (Shapiro y Wilk, 1965), con `scipy.stats.shapiro`.
- Anderson-Darling para normalidad con media y varianza estimadas
  (Stephens, 1974, caso 3). El estadístico se calcula a mano; la decisión usa
  el valor crítico de la tabla de Stephens, por eso `p_value` es null.
- Gráfico de probabilidad normal (Q-Q) con posiciones (j - 0.5)/n,
  Montgomery, cap. 3, sección "Probability Plots".
- Función de autocorrelación muestral r_k y banda ±z_{1-α/2}/√n
  (Montgomery, cap. 10, sección "SPC with Autocorrelated Process Data";
  Box, Jenkins y Reinsel, *Time Series Analysis*).
- Ljung-Box: Q = n(n+2) Σ_{k=1..m} r_k² / (n-k) ~ χ²(m) (Ljung y Box, 1978).
- Prueba de rachas de Wald-Wolfowitz respecto a la mediana, exacta para
  muestras pequeñas y con aproximación normal en las grandes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, Sequence

import numpy as np
from scipy import stats

from .descriptive import Descriptive, Histogram, as_clean_array, build_histogram, describe
from .interpretation import Interpretation, fmt, fmt_p, interpret_assumptions


@dataclass
class TestResult:
    name: str
    null_hypothesis: str
    statistic: float
    p_value: Optional[float]
    critical_value: Optional[float]
    reject: bool
    conclusion: str


@dataclass
class QQPoint:
    theoretical: float
    observed: float


@dataclass
class Autocorrelation:
    lags: list[int]
    values: list[float]
    band: float
    significant_lags: list[int]


@dataclass
class AssumptionsResult:
    """Equivale a `AssumptionsResponse`."""

    descriptive: Descriptive
    normality: list[TestResult]
    is_normal: bool
    qq: list[QQPoint]
    histogram: Histogram
    autocorrelation: Autocorrelation
    independence: list[TestResult]
    is_independent: bool
    interpretation: Interpretation = field(default_factory=lambda: Interpretation(summary=""))


NORMAL_H0 = "Los datos provienen de una distribución normal"
INDEPENDENCE_H0 = "Las observaciones son independientes (no hay autocorrelación)"
RUNS_H0 = "La secuencia de observaciones arriba y abajo de la mediana es aleatoria"


def _decision_text(reject: bool, alpha: float) -> str:
    return (
        f"se rechaza H0 al nivel α = {fmt(alpha, 3)}"
        if reject
        else f"no se rechaza H0 al nivel α = {fmt(alpha, 3)}"
    )


def _check_dispersion(x: np.ndarray) -> None:
    if x.size < 3:
        raise ValueError("Se necesitan al menos 3 observaciones para evaluar supuestos")
    if float(np.ptp(x)) == 0.0:
        raise ValueError(
            "Todas las observaciones son iguales: no hay variación que permita evaluar "
            "normalidad ni independencia. Revise la resolución del instrumento de medición."
        )


# --------------------------------------------------------------------------
# Normalidad
# --------------------------------------------------------------------------


def shapiro_wilk_test(values: Sequence[float], alpha: float = 0.05) -> TestResult:
    """Prueba de Shapiro-Wilk (Shapiro y Wilk, 1965) con `scipy.stats.shapiro`.

    W cercano a 1 indica concordancia con la normal. Se rechaza H0 si p < α.
    """
    x = as_clean_array(values)
    _check_dispersion(x)
    w, p = stats.shapiro(x)
    w, p = float(w), float(p)
    reject = p < alpha
    text = (
        f"W = {fmt(w, 4)}, p = {fmt_p(p)}: {_decision_text(reject, alpha)}. "
        + (
            "Hay evidencia de que los datos no son normales."
            if reject
            else "Los datos son compatibles con una distribución normal."
        )
    )
    if x.size > 5000:
        text += " Con más de 5000 datos el valor p es aproximado y la prueba detecta desvíos mínimos."
    return TestResult(
        name="Shapiro-Wilk",
        null_hypothesis=NORMAL_H0,
        statistic=w,
        p_value=p,
        critical_value=None,
        reject=reject,
        conclusion=text,
    )


# Stephens (1974), caso 3 (media y varianza estimadas). Valores críticos del
# estadístico modificado A²·(1 + 4/n - 25/n²); al dividir por ese factor se
# obtienen en la escala de A². Es la misma tabla que usa scipy.stats.anderson.
_AD_SIGNIFICANCE = np.array([0.15, 0.10, 0.05, 0.025, 0.01])
_AD_CRITICAL_MODIFIED = np.array([0.576, 0.656, 0.787, 0.918, 1.092])


def anderson_darling_statistic(values: Sequence[float]) -> float:
    """A² = -n - (1/n) Σ (2i - 1) [ln Φ(z_(i)) + ln(1 - Φ(z_(n+1-i)))],
    con z = (x - x̄)/s (Stephens, 1974)."""
    x = np.sort(as_clean_array(values))
    n = x.size
    z = (x - x.mean()) / x.std(ddof=1)
    i = np.arange(1, n + 1)
    s = np.sum((2 * i - 1) * (stats.norm.logcdf(z) + stats.norm.logsf(z[::-1])))
    return float(-n - s / n)


def anderson_darling_critical_value(n: int, alpha: float) -> tuple[float, bool]:
    """Valor crítico de A² para el nivel α (Stephens, 1974, caso 3).

    Para α entre 0.01 y 0.15 se interpola linealmente en log(α) entre los
    valores tabulados. Fuera de ese rango se usa el extremo más cercano y el
    segundo valor devuelto es False para advertirlo.
    """
    factor = 1 + 4 / n - 25 / n**2
    crit = _AD_CRITICAL_MODIFIED / factor
    in_table = 0.01 <= alpha <= 0.15
    la = math.log(min(max(alpha, 0.01), 0.15))
    # np.interp necesita x creciente: log(α) crece cuando el crítico baja.
    value = float(np.interp(la, np.log(_AD_SIGNIFICANCE[::-1]), crit[::-1]))
    return value, in_table


def anderson_darling_test(values: Sequence[float], alpha: float = 0.05) -> TestResult:
    """Anderson-Darling para normalidad (parámetros estimados).

    Se rechaza H0 si A² supera el valor crítico. Es más sensible que
    Shapiro-Wilk a desvíos en las colas, que son justamente las que determinan
    la fracción no conforme. Solo da valor crítico: `p_value` es null.
    """
    x = as_clean_array(values)
    _check_dispersion(x)
    a2 = anderson_darling_statistic(x)
    crit, in_table = anderson_darling_critical_value(int(x.size), alpha)
    reject = a2 > crit
    text = (
        f"A² = {fmt(a2, 4)} frente al valor crítico {fmt(crit, 4)} (α = {fmt(alpha, 3)}): "
        f"{_decision_text(reject, alpha)}. "
        + (
            "Las colas de los datos se apartan de la normal."
            if reject
            else "No hay evidencia de desvío de la normalidad, tampoco en las colas."
        )
    )
    if not in_table:
        text += (
            " La tabla de Stephens cubre α entre 0.01 y 0.15; se usó el valor crítico del "
            "extremo más cercano."
        )
    return TestResult(
        name="Anderson-Darling",
        null_hypothesis=NORMAL_H0,
        statistic=a2,
        p_value=None,
        critical_value=crit,
        reject=reject,
        conclusion=text,
    )


def qq_points(values: Sequence[float]) -> list[QQPoint]:
    """Puntos del gráfico de probabilidad normal.

    El j-ésimo valor ordenado se grafica contra el cuantil normal estándar de
    (j - 0.5)/n (Montgomery, cap. 3, "Probability Plots"). Si los datos son
    normales, los puntos quedan sobre una recta de pendiente s y ordenada x̄.
    """
    x = np.sort(as_clean_array(values))
    n = x.size
    q = stats.norm.ppf((np.arange(1, n + 1) - 0.5) / n)
    return [QQPoint(theoretical=float(t), observed=float(o)) for t, o in zip(q, x)]


# --------------------------------------------------------------------------
# Independencia
# --------------------------------------------------------------------------


def default_max_lag(n: int) -> int:
    """min(20, n/4), al menos 1 y como máximo n - 1 (contrato del módulo 4)."""
    return int(max(1, min(20, n // 4, n - 1)))


def acf(values: Sequence[float], max_lag: int) -> np.ndarray:
    """Autocorrelación muestral r_k, k = 1..max_lag.

    r_k = Σ_{t=1}^{n-k} (x_t - x̄)(x_{t+k} - x̄) / Σ_{t=1}^{n} (x_t - x̄)²
    (Montgomery, cap. 10, ecuación de la ACF muestral).
    """
    x = as_clean_array(values)
    n = x.size
    if not 1 <= max_lag <= n - 1:
        raise ValueError(f"max_lag debe estar entre 1 y {n - 1}")
    d = x - x.mean()
    denom = float(np.dot(d, d))
    if denom == 0:
        raise ValueError("Varianza cero: la autocorrelación no está definida")
    return np.array([np.dot(d[: n - k], d[k:]) / denom for k in range(1, max_lag + 1)])


def autocorrelation(
    values: Sequence[float], max_lag: Optional[int] = None, alpha: float = 0.05
) -> Autocorrelation:
    """ACF con banda ±z_{1-α/2}/√n y rezagos que la superan.

    La banda es la aproximación de Bartlett bajo ruido blanco: si la serie es
    independiente, r_k ~ N(0, 1/n) aproximadamente.
    """
    x = as_clean_array(values)
    n = int(x.size)
    m = default_max_lag(n) if max_lag is None else int(min(max_lag, n - 1))
    r = acf(x, m)
    band = float(stats.norm.ppf(1 - alpha / 2) / math.sqrt(n))
    lags = list(range(1, m + 1))
    return Autocorrelation(
        lags=lags,
        values=[float(v) for v in r],
        band=band,
        significant_lags=[k for k, v in zip(lags, r) if abs(v) > band],
    )


def ljung_box_test(
    values: Sequence[float], max_lag: Optional[int] = None, alpha: float = 0.05
) -> TestResult:
    """Prueba de Ljung-Box (Ljung y Box, 1978).

    Q = n(n + 2) Σ_{k=1}^{m} r_k² / (n - k), que bajo H0 sigue χ² con m grados
    de libertad (no se ajusta ningún modelo ARMA, así que no se restan
    parámetros). Se rechaza H0 si p < α.
    """
    x = as_clean_array(values)
    _check_dispersion(x)
    n = int(x.size)
    m = default_max_lag(n) if max_lag is None else int(min(max_lag, n - 1))
    r = acf(x, m)
    k = np.arange(1, m + 1)
    q = float(n * (n + 2) * np.sum(r**2 / (n - k)))
    p = float(stats.chi2.sf(q, m))
    reject = p < alpha
    text = (
        f"Q = {fmt(q, 4)} con {m} rezagos (χ² con {m} g.l.), p = {fmt_p(p)}: "
        f"{_decision_text(reject, alpha)}. "
        + (
            "Las autocorrelaciones de los primeros rezagos, en conjunto, son mayores que las "
            "esperables por azar: las observaciones no son independientes."
            if reject
            else "En conjunto, las autocorrelaciones son compatibles con observaciones independientes."
        )
    )
    return TestResult(
        name="Ljung-Box",
        null_hypothesis=INDEPENDENCE_H0,
        statistic=q,
        p_value=p,
        critical_value=float(stats.chi2.ppf(1 - alpha, m)),
        reject=reject,
        conclusion=text,
    )


def _runs_pmf(n1: int, n2: int) -> dict[int, float]:
    """Distribución exacta del número de rachas R con n1 y n2 elementos de
    cada tipo (Wald y Wolfowitz, 1940):
    P(R = 2k)     = 2·C(n1-1, k-1)·C(n2-1, k-1) / C(n1+n2, n1)
    P(R = 2k + 1) = [C(n1-1, k)·C(n2-1, k-1) + C(n1-1, k-1)·C(n2-1, k)] / C(n1+n2, n1)
    """
    total = math.comb(n1 + n2, n1)
    pmf: dict[int, float] = {}
    for r in range(2, n1 + n2 + 1):
        if r % 2 == 0:
            k = r // 2
            ways = 2 * math.comb(n1 - 1, k - 1) * math.comb(n2 - 1, k - 1)
        else:
            k = (r - 1) // 2
            ways = math.comb(n1 - 1, k) * math.comb(n2 - 1, k - 1) + math.comb(
                n1 - 1, k - 1
            ) * math.comb(n2 - 1, k)
        if ways:
            pmf[r] = ways / total
    return pmf


_EXACT_RUNS_LIMIT = 60  # n1 + n2 hasta el que se usa la distribución exacta


def runs_test(values: Sequence[float], alpha: float = 0.05) -> TestResult:
    """Prueba de rachas respecto a la mediana (Wald-Wolfowitz).

    Cada observación se clasifica arriba (+) o abajo (-) de la mediana; las
    iguales a la mediana se descartan. Con n1 y n2 observaciones de cada lado
    y R rachas observadas:
        E[R] = 2·n1·n2/(n1 + n2) + 1
        Var[R] = 2·n1·n2·(2·n1·n2 - n1 - n2) / [(n1 + n2)²·(n1 + n2 - 1)]
        z = (R - E[R]) / √Var[R]
    El estadístico informado es z. El valor p (bilateral) es exacto si
    n1 + n2 <= 60 y normal en otro caso. Pocas rachas indican agrupamiento,
    tendencias o desplazamientos; demasiadas, oscilación (por ejemplo,
    sobreajuste del operador).
    """
    x = as_clean_array(values)
    _check_dispersion(x)
    med = float(np.median(x))
    signs = np.sign(x - med)
    signs = signs[signs != 0]
    n1 = int(np.sum(signs > 0))
    n2 = int(np.sum(signs < 0))
    if n1 == 0 or n2 == 0:
        return TestResult(
            name="Rachas",
            null_hypothesis=RUNS_H0,
            statistic=0.0,
            p_value=None,
            critical_value=None,
            reject=False,
            conclusion=(
                "No se puede aplicar la prueba de rachas: todas las observaciones distintas de la "
                f"mediana ({fmt(med, 4)}) quedan del mismo lado."
            ),
        )
    runs = int(1 + np.sum(signs[1:] != signs[:-1]))
    m = n1 + n2
    expected = 2 * n1 * n2 / m + 1
    var = 2 * n1 * n2 * (2 * n1 * n2 - n1 - n2) / (m**2 * (m - 1))
    z = (runs - expected) / math.sqrt(var) if var > 0 else 0.0
    if m <= _EXACT_RUNS_LIMIT:
        pmf = _runs_pmf(n1, n2)
        lower = sum(p for r, p in pmf.items() if r <= runs)
        upper = sum(p for r, p in pmf.items() if r >= runs)
        p_value = min(1.0, 2 * min(lower, upper))
        method = "exacto"
    else:
        p_value = float(2 * stats.norm.sf(abs(z)))
        method = "aproximación normal"
    reject = p_value < alpha
    if not reject:
        meaning = "La alternancia arriba y abajo de la mediana es compatible con un proceso aleatorio."
    elif runs < expected:
        meaning = (
            "Hay menos rachas de las esperadas: los datos se agrupan en tramos largos del mismo "
            "lado, señal de tendencias, desplazamientos o autocorrelación positiva."
        )
    else:
        meaning = (
            "Hay más rachas de las esperadas: los datos oscilan de un lado a otro, patrón típico "
            "de sobreajuste del proceso, de muestreo alternado entre dos fuentes o de "
            "autocorrelación negativa."
        )
    return TestResult(
        name="Rachas",
        null_hypothesis=RUNS_H0,
        statistic=float(z),
        p_value=float(p_value),
        critical_value=None,
        reject=reject,
        conclusion=(
            f"{runs} rachas observadas frente a {fmt(expected, 4)} esperadas "
            f"({n1} datos arriba y {n2} abajo de la mediana {fmt(med, 4)}); z = {fmt(z, 3)}, "
            f"p = {fmt_p(p_value)} ({method}): {_decision_text(reject, alpha)}. {meaning}"
        ),
    )


# --------------------------------------------------------------------------
# Análisis completo
# --------------------------------------------------------------------------


def analyze_assumptions(
    values: Sequence[float],
    alpha: float = 0.05,
    max_lag: Optional[int] = None,
    histogram_bins: Optional[int] = None,
) -> AssumptionsResult:
    """Normalidad e independencia de observaciones individuales en orden temporal.

    `is_normal` es True si ni Shapiro-Wilk ni Anderson-Darling rechazan.
    `is_independent` es True si ni Ljung-Box ni la prueba de rachas rechazan
    (los rezagos de la ACF fuera de banda se informan como hallazgos).
    """
    x = as_clean_array(values)
    _check_dispersion(x)
    if not 0 < alpha < 1:
        raise ValueError("alpha debe estar entre 0 y 1")
    normality = [shapiro_wilk_test(x, alpha), anderson_darling_test(x, alpha)]
    ac = autocorrelation(x, max_lag, alpha)
    independence = [ljung_box_test(x, len(ac.lags), alpha), runs_test(x, alpha)]
    result = AssumptionsResult(
        descriptive=describe(x),
        normality=normality,
        is_normal=not any(t.reject for t in normality),
        qq=qq_points(x),
        histogram=build_histogram(x, histogram_bins),
        autocorrelation=ac,
        independence=independence,
        is_independent=not any(t.reject for t in independence),
    )
    result.interpretation = interpret_assumptions(result, alpha=alpha)
    return result
