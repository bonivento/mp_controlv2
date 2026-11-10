"""Capacidad del proceso: Cp, Cpk, Pp, Ppk, Cpm, intervalos y fracción no conforme.

Fuente: Montgomery, *Introduction to Statistical Quality Control*, cap. 8
("Process and Measurement System Capability Analysis"):

- Capacidad potencial con sigma de corto plazo (dentro de subgrupos):
      Cp  = (USL - LSL) / (6σ_w)
      Cpu = (USL - μ) / (3σ_w),   Cpl = (μ - LSL) / (3σ_w),   Cpk = min(Cpu, Cpl)
- Desempeño con sigma de largo plazo (desviación muestral de todos los datos):
  Pp, Ppu, Ppl y Ppk con las mismas fórmulas y σ_o. Montgomery advierte que
  Pp y Ppk solo describen el pasado si el proceso no está en control.
- Cpm (índice de Taguchi): Cpm = (USL - LSL) / (6τ), τ = √(σ² + (μ - T)²).
  Se usa la forma general min(T - LSL, USL - T) / (3τ), que coincide con la
  anterior cuando T es el punto medio y admite una sola especificación.
  τ se calcula con σ de largo plazo (como Minitab), ver dudas en el reporte.
- Intervalo para Cp (chi-cuadrado), Montgomery, sección de intervalos de confianza para los índices (8.3.5 en la 6.ª ed.):
      Ĉp·√(χ²_{α/2, n-1} / (n-1)) <= Cp <= Ĉp·√(χ²_{1-α/2, n-1} / (n-1))
  (cuantiles inferior y superior de la chi-cuadrado). Con σ_w estimada por
  R̄/d2 o S̄/c4 el intervalo es aproximado.
- Intervalo para Cpk (aproximación de Bissell, 1990), sección de intervalos de confianza para los índices (8.3.5 en la 6.ª ed.):
      Ĉpk·[1 ∓ z_{α/2}·√(1/(9n·Ĉpk²) + 1/(2(n-1)))]
  Se aplica también a Cpu, Cpl, Ppu, Ppl y Ppk (índices unilaterales).
- Fracción no conforme esperada con el modelo normal:
      P(x < LSL) = Φ((LSL - μ)/σ),   P(x > USL) = 1 - Φ((USL - μ)/σ),
  con σ_w y con σ_o; la observada es el conteo directo.

Sigma de corto plazo, en orden (contrato `CapabilityRequest`):
1. `limits` congelados de Fase I: sigma = params["sigma"].
2. Subgrupos con n >= 2: R̄/d2 (por defecto si n es constante y <= 10) o
   S̄/c4 (por defecto si n > 10 o variable). Con n variable se promedia
   R_i/d2(n_i) o S_i/c4(n_i) (Montgomery, cap. 6, X-barra y S con n variable).
3. Subgrupos con n = 1: MR̄/d2 con d2(2) = 1.128 (sección 6.4).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

import numpy as np
from scipy import stats

from .constants import c4, d2
from .descriptive import Histogram, build_histogram, flatten_subgroups
from .interpretation import Interpretation, interpret_capability


@dataclass
class IndexValue:
    value: Optional[float]
    lower: Optional[float] = None
    upper: Optional[float] = None


@dataclass
class NonConforming:
    below_lsl: Optional[float]
    above_usl: Optional[float]
    total: float
    ppm: float


@dataclass
class CapabilityResult:
    """Equivale a `CapabilityResponse`."""

    n: int
    mean: float
    sigma_within: float
    sigma_overall: float
    sigma_method: str
    cp: IndexValue
    cpl: IndexValue
    cpu: IndexValue
    cpk: IndexValue
    pp: IndexValue
    ppl: IndexValue
    ppu: IndexValue
    ppk: IndexValue
    cpm: IndexValue
    expected_within: NonConforming
    expected_overall: NonConforming
    observed: NonConforming
    histogram: Histogram
    verdict: str
    interpretation: Interpretation = field(default_factory=lambda: Interpretation(summary=""))


# --------------------------------------------------------------------------
# Sigma de corto plazo
# --------------------------------------------------------------------------


def _limits_param(limits: Any, key: str) -> Optional[float]:
    params = limits.get("params") if isinstance(limits, dict) else getattr(limits, "params", None)
    if params is None:
        return None
    v = params.get(key) if isinstance(params, dict) else getattr(params, key, None)
    return None if v is None else float(v)


def _limits_chart(limits: Any) -> Optional[str]:
    return limits.get("chart_type") if isinstance(limits, dict) else getattr(limits, "chart_type", None)


def sigma_rbar_d2(subgroups: Sequence[Sequence[float]]) -> float:
    """σ = promedio de R_i/d2(n_i); con n constante es R̄/d2 (Montgomery, sección 6.2.1)."""
    return float(np.mean([np.ptp(np.asarray(g, float)) / d2(len(g)) for g in subgroups]))


def sigma_sbar_c4(subgroups: Sequence[Sequence[float]]) -> float:
    """σ = promedio de S_i/c4(n_i); con n constante es S̄/c4 (Montgomery, sección 6.3.1)."""
    return float(np.mean([np.std(np.asarray(g, float), ddof=1) / c4(len(g)) for g in subgroups]))


def sigma_mrbar_d2(values: Sequence[float]) -> float:
    """σ = MR̄/d2(2), con MR_i = |x_i - x_{i-1}| (Montgomery, sección 6.4)."""
    x = np.asarray(values, dtype=float)
    if x.size < 2:
        raise ValueError("Se necesitan al menos 2 observaciones para el rango móvil")
    return float(np.mean(np.abs(np.diff(x))) / d2(2))


def short_term_sigma(
    subgroups: Sequence[Sequence[float]],
    sigma_method: Optional[str] = None,
    limits: Any = None,
) -> tuple[float, str]:
    """Sigma de corto plazo y el método usado, según el contrato del módulo 5."""
    if limits is not None:
        chart = _limits_chart(limits)
        if chart is not None and chart not in ("xbar_r", "xbar_s", "i_mr"):
            raise ValueError(
                "Los límites congelados deben venir de un gráfico por variables (X-barra-R, X-barra-S o I-MR)"
            )
        s = _limits_param(limits, "sigma")
        if s is None:
            raise ValueError("Los límites congelados no traen 'sigma' en params")
        return s, "frozen_limits"
    sizes = {len(g) for g in subgroups}
    if 1 in sizes and len(sizes) > 1:
        raise ValueError("Hay subgrupos de una observación mezclados con subgrupos mayores")
    if sizes == {1}:
        if sigma_method not in (None, "mrbar_d2"):
            raise ValueError("Con observaciones individuales (n = 1) la sigma de corto plazo es MR̄/d2")
        return sigma_mrbar_d2([g[0] for g in subgroups]), "mrbar_d2"
    if sigma_method == "mrbar_d2":
        raise ValueError("MR̄/d2 solo aplica a observaciones individuales (n = 1)")
    if sigma_method is None:
        sigma_method = "rbar_d2" if len(sizes) == 1 and max(sizes) <= 10 else "sbar_c4"
    if sigma_method == "rbar_d2":
        return sigma_rbar_d2(subgroups), "rbar_d2"
    if sigma_method == "sbar_c4":
        return sigma_sbar_c4(subgroups), "sbar_c4"
    raise ValueError(f"Método de sigma desconocido: {sigma_method!r}")


# --------------------------------------------------------------------------
# Índices e intervalos
# --------------------------------------------------------------------------


def cp_confidence_interval(cp: float, n: int, confidence: float = 0.95) -> tuple[float, float]:
    """Intervalo chi-cuadrado para Cp con n - 1 grados de libertad (Montgomery, cap. 8, intervalos de confianza para los índices; 8.3.5 en la 6.ª ed.)."""
    a = 1 - confidence
    df = n - 1
    lo = cp * math.sqrt(stats.chi2.ppf(a / 2, df) / df)
    hi = cp * math.sqrt(stats.chi2.ppf(1 - a / 2, df) / df)
    return float(lo), float(hi)


def bissell_interval(index: float, n: int, confidence: float = 0.95) -> Optional[tuple[float, float]]:
    """Intervalo aproximado de Bissell para Cpk (o un índice unilateral):
    Ĉ·[1 ∓ z_{α/2}·√(1/(9n·Ĉ²) + 1/(2(n-1)))] (Montgomery, cap. 8, intervalos de confianza para los índices; 8.3.5 en la 6.ª ed.).
    None si Ĉ = 0 (la aproximación no está definida)."""
    if index == 0:
        return None
    z = stats.norm.ppf(1 - (1 - confidence) / 2)
    w = z * math.sqrt(1 / (9 * n * index**2) + 1 / (2 * (n - 1)))
    lo, hi = index * (1 - w), index * (1 + w)
    return float(min(lo, hi)), float(max(lo, hi))


def _indices(mean: float, sigma: float, lsl, usl, n: int, confidence: float):
    """(C, Cl, Cu, Ck) con sus intervalos para un sigma dado."""
    both = lsl is not None and usl is not None
    if both:
        c = (usl - lsl) / (6 * sigma)
        lo, hi = cp_confidence_interval(c, n, confidence)
        cp = IndexValue(c, lo, hi)
    else:
        cp = IndexValue(None)

    def one_sided(v):
        if v is None:
            return IndexValue(None)
        ci = bissell_interval(v, n, confidence)
        return IndexValue(v, *(ci if ci else (None, None)))

    cl_v = (mean - lsl) / (3 * sigma) if lsl is not None else None
    cu_v = (usl - mean) / (3 * sigma) if usl is not None else None
    ck_v = min(v for v in (cl_v, cu_v) if v is not None)
    return cp, one_sided(cl_v), one_sided(cu_v), one_sided(ck_v)


def expected_nonconforming(mean: float, sigma: float, lsl, usl) -> NonConforming:
    """Fracción fuera de especificación con el modelo normal (Montgomery, cap. 8)."""
    below = float(stats.norm.cdf((lsl - mean) / sigma)) if lsl is not None else None
    above = float(stats.norm.sf((usl - mean) / sigma)) if usl is not None else None
    total = (below or 0.0) + (above or 0.0)
    return NonConforming(below, above, total, total * 1e6)


def observed_nonconforming(x: np.ndarray, lsl, usl) -> NonConforming:
    """Conteo directo de observaciones fuera de especificación."""
    n = x.size
    below = float(np.sum(x < lsl) / n) if lsl is not None else None
    above = float(np.sum(x > usl) / n) if usl is not None else None
    total = (below or 0.0) + (above or 0.0)
    return NonConforming(below, above, total, total * 1e6)


def capability_verdict(cpk: float) -> str:
    """inadequate (< 1), marginal (1 a 1.33), adequate (1.33 a 1.67), excellent (>= 1.67)."""
    if cpk < 1.0:
        return "inadequate"
    if cpk < 1.33:
        return "marginal"
    if cpk < 1.67:
        return "adequate"
    return "excellent"


def analyze_capability(
    subgroups: Sequence[Sequence[float]],
    lsl: Optional[float] = None,
    usl: Optional[float] = None,
    target: Optional[float] = None,
    limits: Any = None,
    sigma_method: Optional[str] = None,
    confidence: float = 0.95,
    is_stable: Optional[bool] = None,
    is_normal: Optional[bool] = None,
    histogram_bins: Optional[int] = None,
) -> CapabilityResult:
    """Análisis de capacidad completo (equivale a `CapabilityResponse`).

    Con una sola especificación, Cp, Pp y el índice del lado faltante van en
    null. Si `is_stable` o `is_normal` son False se calcula igual y la
    interpretación advierte que los índices no son confiables.
    """
    if lsl is None and usl is None:
        raise ValueError("Se requiere al menos un límite de especificación (LSL o USL)")
    if lsl is not None and usl is not None and lsl >= usl:
        raise ValueError("LSL debe ser menor que USL")
    if not 0 < confidence < 1:
        raise ValueError("El nivel de confianza debe estar entre 0 y 1")
    x = flatten_subgroups(subgroups)
    n = int(x.size)
    if n < 2:
        raise ValueError("Se necesitan al menos 2 observaciones")
    mean = float(x.mean())
    sigma_o = float(x.std(ddof=1))
    sigma_w, method = short_term_sigma(subgroups, sigma_method, limits)
    if not (sigma_w > 0 and sigma_o > 0):
        raise ValueError(
            "La dispersión es cero (todas las observaciones o todos los subgrupos son iguales): "
            "los índices de capacidad no están definidos. Revise la resolución del instrumento."
        )

    cp, cpl, cpu, cpk = _indices(mean, sigma_w, lsl, usl, n, confidence)
    pp, ppl, ppu, ppk = _indices(mean, sigma_o, lsl, usl, n, confidence)

    cpm = IndexValue(None)
    if target is not None:
        tau = math.sqrt(sigma_o**2 + (mean - target) ** 2)
        halves = [h for h in ((target - lsl) if lsl is not None else None,
                              (usl - target) if usl is not None else None) if h is not None]
        cpm = IndexValue(min(halves) / (3 * tau))

    result = CapabilityResult(
        n=n,
        mean=mean,
        sigma_within=sigma_w,
        sigma_overall=sigma_o,
        sigma_method=method,
        cp=cp,
        cpl=cpl,
        cpu=cpu,
        cpk=cpk,
        pp=pp,
        ppl=ppl,
        ppu=ppu,
        ppk=ppk,
        cpm=cpm,
        expected_within=expected_nonconforming(mean, sigma_w, lsl, usl),
        expected_overall=expected_nonconforming(mean, sigma_o, lsl, usl),
        observed=observed_nonconforming(x, lsl, usl),
        histogram=build_histogram(x, histogram_bins, extend_to=(lsl, usl, target)),
        verdict=capability_verdict(float(cpk.value)),
    )
    result.interpretation = interpret_capability(
        result,
        lsl=lsl,
        usl=usl,
        target=target,
        confidence=confidence,
        is_stable=is_stable,
        is_normal=is_normal,
        subgroup_count=len(subgroups),
    )
    return result
