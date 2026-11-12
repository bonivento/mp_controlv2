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
      Ĉp·√(χ²_{α/2, ν} / ν) <= Cp <= Ĉp·√(χ²_{1-α/2, ν} / ν)
  Montgomery lo da con ν = n - 1 porque σ se estima con la desviación muestral.
  Aquí ν son los grados de libertad efectivos del estimador de sigma que se
  usó (ver `sigma_dof`): ν·σ̂²/σ² se aproxima con una χ²_ν cuyo coeficiente de
  variación coincide con el de σ̂ (aproximación de Patnaik, 1949), es decir
  ν = 1 / (2·CV²(σ̂)). Con la desviación muestral ν = n - 1 y el intervalo es
  exacto; con R̄/d2, S̄/c4, MR̄/d2 o límites congelados es aproximado.
- Intervalo para Cpk (aproximación de Bissell, 1990), sección de intervalos de confianza para los índices (8.3.5 en la 6.ª ed.):
      Ĉpk·[1 ∓ z_{α/2}·√(1/(9n·Ĉpk²) + 1/(2ν))]
  El término 1/(9n) viene de estimar la media con los n datos y 1/(2ν) de
  estimar sigma, por eso con sigma de corto plazo se usa ν efectivo y con
  sigma de largo plazo ν = n - 1 (la fórmula del libro). Se aplica también a
  Cpu, Cpl, Ppu, Ppl y Ppk (índices unilaterales).
- Fracción no conforme esperada con el modelo normal:
      P(x < LSL) = Φ((LSL - μ)/σ),   P(x > USL) = 1 - Φ((USL - μ)/σ),
  con σ_w y con σ_o; la observada es el conteo directo.

Sigma de corto plazo, en orden (contrato `CapabilityRequest`):
1. `limits` congelados de Fase I: sigma = params["sigma"].
2. Subgrupos con n >= 2: R̄/d2 (por defecto si n es constante y <= 10) o
   S̄/c4 (por defecto si n > 10 o variable). Con n variable y S, se usa la
   desviación combinada ponderada por n_i - 1, s_p = √(Σ(n_i - 1)S_i² / Σ(n_i - 1))
   (Montgomery, sección 6.3.2, gráficos X-barra y S con tamaño de muestra
   variable), corregida por c4(ν + 1) con ν = Σ(n_i - 1) para que sea insesgada.
   Con n variable y R (solo si se pide), se promedia R_i/d2(n_i): es insesgado
   pero ineficiente, y no es la recomendación del libro.
3. Subgrupos con n = 1: MR̄/d2 con d2(2) = 1.128 (sección 6.4).

Grados de libertad efectivos ν del estimador de sigma de corto plazo
(ν = 1/(2·CV²), CV = desviación estándar del estimador / sigma):
- R̄/d2 con m subgrupos de tamaño n: Var(R̄/d2) = σ²·d3²/(m·d2²), así que
  ν = m·d2²/(2·d3²) (≈ 0.9·m(n - 1) para n = 5). Con n variable,
  ν = m² / (2·Σ(d3_i/d2_i)²). Fuente de d2 y d3: Montgomery, apéndice VI.
- S̄/c4 con m subgrupos de tamaño n: Var(S_i) = σ²(1 - c4²), así que
  ν = m·c4² / (2·(1 - c4²)); para n = 5 da 3.79·m ≈ 0.95·m(n - 1), el valor
  que cita el validador. Con n variable (desviación combinada) ν = Σ(n_i - 1),
  exacto porque ν·s_p²/σ² ~ χ²_ν.
- MR̄/d2 con k = N - 1 rangos móviles consecutivos: los MR vecinos comparten
  una observación y están correlacionados. Con U = x_i - x_{i-1} y
  V = x_{i+1} - x_i (correlación -1/2), E|U||V| = σ²(2√3/π + 1/3), de modo que
  Cov(MR_i, MR_{i+1}) = σ²((2√3 - 4)/π + 1/3) = 0.16275σ² y
  Var(MR̄) = σ²[k·d3(2)² + 2(k - 1)·0.16275]/k². Cuando k crece, ν tiende a
  d2(2)²/(2(d3(2)² + 2·0.16275))·k = 0.6050·k, el 0.61(N - 1) que midió el
  validador por simulación. Si hubo exclusiones, solo entran los MR con sus dos
  puntos retenidos y solo los pares de MR vecinos que efectivamente comparten
  una observación: Var(MR̄) = σ²[k·d3(2)² + 2v·0.16275]/k², con v el número
  de esos pares.
- Límites congelados: sigma viene de la Fase I, así que ν es el de esa
  estimación, reconstruido con `points_used`, `subgroup_size` y
  `sigma_method` (o el tipo de gráfico) de los límites. Si faltan, ν es
  desconocido y los intervalos de Cp y Cpk van en null.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

import numpy as np
from scipy import stats

from .constants import c4, d2, d3
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
    """σ de corto plazo con desviaciones estándar de subgrupo.

    - n constante: S̄/c4(n) (Montgomery, sección 6.3.1).
    - n variable: s_p/c4(ν + 1), con s_p = √(Σ(n_i - 1)S_i²/ν) y ν = Σ(n_i - 1),
      la desviación combinada de Montgomery, sección 6.3.2, corregida por sesgo
      (E[s_p] = c4(ν + 1)·σ porque ν·s_p²/σ² ~ χ²_ν).
    """
    groups = [np.asarray(g, float) for g in subgroups]
    sizes = {g.size for g in groups}
    if len(sizes) == 1:
        return float(np.mean([np.std(g, ddof=1) / c4(g.size) for g in groups]))
    nu = sum(g.size - 1 for g in groups)
    sp = math.sqrt(sum((g.size - 1) * np.var(g, ddof=1) for g in groups) / nu)
    return float(sp / c4(nu + 1))


# Cov(MR_i, MR_{i+1}) / σ² para datos normales independientes: (2√3 - 4)/π + 1/3.
_MR_LAG1_COV = (2 * math.sqrt(3) - 4) / math.pi + 1 / 3


def _dof_rbar(sizes: Sequence[int]) -> float:
    """ν = m² / (2·Σ(d3_i/d2_i)²); con n constante, m·d2²/(2·d3²)."""
    m = len(sizes)
    return m**2 / (2 * sum((d3(n) / d2(n)) ** 2 for n in sizes))


def _dof_sbar(sizes: Sequence[int]) -> float:
    """S̄/c4 con n constante: ν = m·c4²/(2(1 - c4²)); con n variable
    (desviación combinada): ν = Σ(n_i - 1)."""
    if len(set(sizes)) == 1:
        c = c4(sizes[0])
        return len(sizes) * c**2 / (2 * (1 - c**2))
    return float(sum(n - 1 for n in sizes))


def _dof_mrbar(k: int, neighbours: Optional[int] = None) -> float:
    """ν de MR̄/d2 con k rangos móviles; `neighbours` es el número de pares de
    MR consecutivos que comparten una observación (k - 1 si no hubo huecos)."""
    if k < 1:
        raise ValueError("Se necesita al menos un rango móvil")
    v = k - 1 if neighbours is None else int(neighbours)
    var_mrbar = (k * d3(2) ** 2 + 2 * v * _MR_LAG1_COV) / k**2
    return d2(2) ** 2 / (2 * var_mrbar)


def _mr_counts_with_exclusions(total: int, excluded: set[int]) -> tuple[int, int]:
    """(k, v) para una serie de `total` individuales con `excluded` fuera del
    cálculo: k = MR con sus dos puntos retenidos (MR_i = |x_i - x_{i-1}|) y
    v = pares (MR_i, MR_{i+1}) con ambos en el promedio."""
    keep = [i not in excluded for i in range(total)]
    used = [keep[i] and keep[i - 1] for i in range(1, total)]
    k = sum(used)
    v = sum(1 for j in range(1, len(used)) if used[j] and used[j - 1])
    return k, v


def sigma_dof(
    subgroups: Sequence[Sequence[float]], method: str, limits: Any = None
) -> Optional[float]:
    """Grados de libertad efectivos del estimador de sigma de corto plazo.

    `method` es el que devolvió `short_term_sigma`. Con límites congelados se
    reconstruye el ν de la Fase I; si los límites no traen la información
    necesaria devuelve None (los intervalos de Cp y Cpk no se calculan).
    """
    if method == "frozen_limits":
        return frozen_sigma_dof(limits)
    sizes = [len(g) for g in subgroups]
    if method == "mrbar_d2":
        return _dof_mrbar(len(sizes) - 1)
    if method == "rbar_d2":
        return _dof_rbar(sizes)
    if method == "sbar_c4":
        return _dof_sbar(sizes)
    raise ValueError(f"Método de sigma desconocido: {method!r}")


_CHART_SIGMA_METHOD = {"xbar_r": "rbar_d2", "xbar_s": "sbar_c4", "i_mr": "mrbar_d2"}


def _limits_field(limits: Any, key: str) -> Any:
    return limits.get(key) if isinstance(limits, dict) else getattr(limits, key, None)


def _excluded_indices(limits: Any) -> Optional[list[int]]:
    """Índices de `excluded` de los límites (dicts, objetos o enteros); None si
    alguno no trae un índice entero."""
    out = []
    for e in _limits_field(limits, "excluded") or []:
        idx = e if isinstance(e, (int, np.integer)) else (
            e.get("index") if isinstance(e, dict) else getattr(e, "index", None))
        if idx is None or isinstance(idx, bool):
            return None
        try:
            out.append(int(idx))
        except (TypeError, ValueError):
            return None
    return out


def frozen_sigma_dof(limits: Any) -> Optional[float]:
    """ν de la sigma congelada, con m = `points_used`, n = `subgroup_size` y
    el método de `sigma_method` (o, si falta, el del tipo de gráfico).

    En I-MR la Fase I tuvo `points_used` + len(`excluded`) individuales y MR̄
    promedió solo los rangos móviles con sus dos puntos retenidos: con la lista
    `excluded` se cuentan esos rangos y los pares de rangos vecinos que existen
    (hallazgo H26). Si los índices no son coherentes con ese total, se usa la
    serie sin huecos (points_used - 1 rangos), que sobrestima ν levemente.
    """
    if limits is None:
        return None
    method = _limits_field(limits, "sigma_method") or _CHART_SIGMA_METHOD.get(_limits_chart(limits) or "")
    m = _limits_field(limits, "points_used")
    if method is None or m is None or int(m) < 2:
        return None
    m = int(m)
    if method == "mrbar_d2":
        excl = _excluded_indices(limits)
        if excl:
            total = m + len(set(excl))
            if len(set(excl)) == len(excl) and all(0 <= i < total for i in excl):
                k, v = _mr_counts_with_exclusions(total, set(excl))
                if k >= 1:
                    return _dof_mrbar(k, v)
        return _dof_mrbar(m - 1)
    n = _limits_field(limits, "subgroup_size")
    if n is None or int(n) < 2:
        return None
    n = int(n)
    if method == "rbar_d2":
        return _dof_rbar([n] * m)
    if method == "sbar_c4":
        return _dof_sbar([n] * m)
    return None


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


def cp_confidence_interval(
    cp: float, n: int, confidence: float = 0.95, dof: Optional[float] = None
) -> tuple[float, float]:
    """Intervalo chi-cuadrado para Cp (Montgomery, cap. 8, intervalos de confianza para los índices; 8.3.5 en la 6.ª ed.):
    Ĉp·√(χ²_{α/2, ν}/ν) a Ĉp·√(χ²_{1-α/2, ν}/ν).

    `dof` es ν, los grados de libertad del estimador de sigma; si no se da,
    ν = n - 1 (desviación muestral de n datos, el caso del libro). Con otro
    estimador de sigma hay que pasar su ν efectivo (`sigma_dof`): usar n - 1
    con R̄/d2, MR̄/d2 o sigma congelada da intervalos demasiado estrechos
    (cobertura real de 0.60 a 0.92 en lugar de 0.95, hallazgo H1).
    """
    a = 1 - confidence
    df = (n - 1) if dof is None else float(dof)
    if not df > 0:
        raise ValueError("Los grados de libertad deben ser positivos")
    lo = cp * math.sqrt(stats.chi2.ppf(a / 2, df) / df)
    hi = cp * math.sqrt(stats.chi2.ppf(1 - a / 2, df) / df)
    return float(lo), float(hi)


def bissell_interval(
    index: float, n: int, confidence: float = 0.95, dof: Optional[float] = None
) -> Optional[tuple[float, float]]:
    """Intervalo aproximado de Bissell para Cpk (o un índice unilateral):
    Ĉ ∓ z_{α/2}·√(1/(9n) + Ĉ²/(2ν)) (Montgomery, cap. 8, intervalos de confianza para los índices; 8.3.5 en la 6.ª ed.).

    n es el número de datos con que se estimó la media y ν (`dof`) los grados
    de libertad del estimador de sigma; si no se da, ν = n - 1 (el libro).
    None si Ĉ = 0 (la aproximación no está definida en la forma multiplicativa).
    """
    if index == 0:
        return None
    df = (n - 1) if dof is None else float(dof)
    if not df > 0:
        raise ValueError("Los grados de libertad deben ser positivos")
    z = stats.norm.ppf(1 - (1 - confidence) / 2)
    w = z * math.sqrt(1 / (9 * n * index**2) + 1 / (2 * df))
    lo, hi = index * (1 - w), index * (1 + w)
    return float(min(lo, hi)), float(max(lo, hi))


def _indices(mean: float, sigma: float, lsl, usl, n: int, confidence: float, dof: Optional[float],
             with_ci: bool = True):
    """(C, Cl, Cu, Ck) con sus intervalos para un sigma dado con ν = `dof`.
    Con `with_ci` False (ν desconocido) los intervalos van en null."""
    both = lsl is not None and usl is not None
    if both:
        c = (usl - lsl) / (6 * sigma)
        cp = IndexValue(c, *cp_confidence_interval(c, n, confidence, dof)) if with_ci else IndexValue(c)
    else:
        cp = IndexValue(None)

    def one_sided(v):
        if v is None:
            return IndexValue(None)
        ci = bissell_interval(v, n, confidence, dof) if with_ci else None
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
    """inadequate (< 1), marginal (1 a 1.33), adequate (1.33 a 1.67), excellent (>= 1.67).

    Es una escala de uso común (la del contrato), no una tabla de Montgomery:
    el libro (cap. 8, tabla de valores mínimos recomendados del índice) pide
    1.33 para procesos existentes con especificación bilateral y 1.25 con
    especificación unilateral. Rechaza valores no finitos: NaN no cae en
    ninguna categoría.
    """
    if cpk is None or not math.isfinite(float(cpk)):
        raise ValueError("Cpk no es un número finito: no se puede asignar un veredicto de capacidad")
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
    interpretación advierte que los índices no son confiables. LSL, USL y el
    objetivo deben ser finitos; un objetivo fuera de especificación deja Cpm en
    null. Los intervalos de Cp y Cpk usan los grados de libertad efectivos de
    la sigma de corto plazo (`sigma_dof`) y los de Pp y Ppk, N - 1.
    """
    if lsl is None and usl is None:
        raise ValueError("Se requiere al menos un límite de especificación (LSL o USL)")
    for name, v in (("LSL", lsl), ("USL", usl), ("El objetivo", target)):
        if v is not None and not math.isfinite(float(v)):
            raise ValueError(f"{name} debe ser un número finito")
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

    nu_w = sigma_dof(subgroups, method, limits)
    cp, cpl, cpu, cpk = _indices(mean, sigma_w, lsl, usl, n, confidence, nu_w, with_ci=nu_w is not None)
    pp, ppl, ppu, ppk = _indices(mean, sigma_o, lsl, usl, n, confidence, n - 1)

    # Cpm solo si el objetivo está dentro de las especificaciones: fuera de
    # ellas min(T - LSL, USL - T) es negativo y el índice no tiene sentido
    # (hallazgo H14); la interpretación lo advierte.
    cpm = IndexValue(None)
    target_inside = target is not None and (lsl is None or target >= lsl) and (usl is None or target <= usl)
    if target_inside:
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
        sigma_dof=nu_w,
        limits=limits,
    )
    return result
