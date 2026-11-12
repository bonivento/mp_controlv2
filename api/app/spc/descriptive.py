"""Estadística descriptiva, resumen por subgrupo y marcado de atípicos.

También define las estructuras que comparten los demás módulos de análisis
(histograma con curva normal y puntos de curva), para no repetirlas.

Fuentes:
- Montgomery, D. C., *Introduction to Statistical Quality Control*, cap. 3
  ("Modeling Process Quality"): media, desviación estándar muestral,
  cuartiles, diagrama de caja e histograma.
- Tukey (1977), criterio de cercas Q1 - 1.5·IQR y Q3 + 1.5·IQR, el mismo que
  usa el diagrama de caja de Montgomery, cap. 3.
- Regla de Sturges para el número de clases: k = ceil(log2 n) + 1
  (Montgomery, cap. 3, sección del histograma).

Todas las funciones devuelven dataclasses cuyos campos coinciden con los
esquemas de `app/schemas/data.py` y `app/schemas/assumptions.py`; se
convierten con `dataclasses.asdict`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, Sequence

import numpy as np
from scipy import stats


# --------------------------------------------------------------------------
# Estructuras compartidas
# --------------------------------------------------------------------------


@dataclass
class CurvePoint:
    """Punto (x, y) de una curva (OC, AOQ, ATI, ASN, ARL)."""

    x: float
    y: float


@dataclass
class Histogram:
    """Histograma con la curva normal ajustada en escala de frecuencia."""

    edges: list[float]
    counts: list[int]
    normal_curve_x: list[float]
    normal_curve_y: list[float]


@dataclass
class Descriptive:
    count: int
    mean: float
    std: float
    min: float
    q1: float
    median: float
    q3: float
    max: float
    skewness: Optional[float]
    kurtosis: Optional[float]


@dataclass
class SubgroupSummary:
    label: str
    n: int
    mean: float
    range: Optional[float]
    std: Optional[float]
    min: float
    max: float


@dataclass
class OutlierFlag:
    subgroup_index: int
    position: int
    value: float
    reason: str


@dataclass
class SummaryResult:
    """Equivale a `SummaryResponse`."""

    subgroups: list[SubgroupSummary]
    overall: Descriptive
    constant_size: bool
    outliers: list[OutlierFlag] = field(default_factory=list)


# --------------------------------------------------------------------------
# Utilidades numéricas
# --------------------------------------------------------------------------


def finite_or_none(x: Optional[float]) -> Optional[float]:
    """Devuelve `float(x)` si es finito; si es NaN, infinito o None, None."""
    if x is None:
        return None
    x = float(x)
    return x if math.isfinite(x) else None


def as_clean_array(values: Sequence[float], name: str = "values") -> np.ndarray:
    """Convierte a arreglo float 1-D y rechaza NaN o infinitos."""
    arr = np.asarray(values, dtype=float).ravel()
    if arr.size == 0:
        raise ValueError(f"'{name}' no tiene observaciones")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"'{name}' contiene valores vacíos, NaN o infinitos")
    return arr


def flatten_subgroups(subgroups: Sequence[Sequence[float]]) -> np.ndarray:
    """Une los subgrupos en un solo arreglo, en orden de llegada."""
    if len(subgroups) == 0:
        raise ValueError("No hay subgrupos")
    parts = []
    for i, g in enumerate(subgroups):
        arr = np.asarray(g, dtype=float).ravel()
        if arr.size == 0:
            raise ValueError(f"El subgrupo {i + 1} está vacío")
        if not np.all(np.isfinite(arr)):
            raise ValueError(f"El subgrupo {i + 1} contiene valores vacíos, NaN o infinitos")
        parts.append(arr)
    return np.concatenate(parts)


# --------------------------------------------------------------------------
# Descriptiva
# --------------------------------------------------------------------------


def describe(values: Sequence[float]) -> Descriptive:
    """Estadística descriptiva de un conjunto de observaciones.

    - `std`: desviación estándar muestral, divisor n - 1 (Montgomery, cap. 3).
      Con una sola observación se informa 0.
    - Cuartiles: interpolación lineal (tipo 7 de Hyndman y Fan, igual que
      `QUARTILE.INC` de Excel).
    - `skewness`: coeficiente de asimetría muestral ajustado (G1), requiere n >= 3.
    - `kurtosis`: exceso de curtosis muestral ajustado (G2), requiere n >= 4.
    Ambos son null si no hay suficientes datos o si la dispersión es cero.
    """
    x = as_clean_array(values)
    n = int(x.size)
    std = float(np.std(x, ddof=1)) if n > 1 else 0.0
    q1, med, q3 = (float(v) for v in np.percentile(x, [25, 50, 75]))
    skew = kurt = None
    if std > 0:
        if n >= 3:
            skew = finite_or_none(stats.skew(x, bias=False))
        if n >= 4:
            kurt = finite_or_none(stats.kurtosis(x, fisher=True, bias=False))
    return Descriptive(
        count=n,
        mean=float(np.mean(x)),
        std=std,
        min=float(np.min(x)),
        q1=q1,
        median=med,
        q3=q3,
        max=float(np.max(x)),
        skewness=skew,
        kurtosis=kurt,
    )


def summarize_subgroups(
    subgroups: Sequence[Sequence[float]], labels: Optional[Sequence[str]] = None
) -> list[SubgroupSummary]:
    """Media, rango, desviación muestral, mínimo y máximo de cada subgrupo.

    Rango y desviación son null cuando el subgrupo tiene una sola observación.
    Si no se envían etiquetas, se numeran desde 1.
    """
    flatten_subgroups(subgroups)  # valida
    if labels is not None and len(labels) != len(subgroups):
        raise ValueError("La cantidad de etiquetas no coincide con la de subgrupos")
    out = []
    for i, g in enumerate(subgroups):
        arr = np.asarray(g, dtype=float).ravel()
        n = int(arr.size)
        out.append(
            SubgroupSummary(
                label=str(labels[i]) if labels is not None else str(i + 1),
                n=n,
                mean=float(arr.mean()),
                range=float(arr.max() - arr.min()) if n > 1 else None,
                std=float(arr.std(ddof=1)) if n > 1 else None,
                min=float(arr.min()),
                max=float(arr.max()),
            )
        )
    return out


def tukey_fences(values: Sequence[float], k: float = 1.5) -> tuple[float, float]:
    """Cercas de Tukey (Q1 - k·IQR, Q3 + k·IQR). Montgomery, cap. 3 (diagrama de caja)."""
    x = as_clean_array(values)
    q1, q3 = np.percentile(x, [25, 75])
    iqr = q3 - q1
    return float(q1 - k * iqr), float(q3 + k * iqr)


def flag_outliers_iqr(
    subgroups: Sequence[Sequence[float]],
    labels: Optional[Sequence[str]] = None,
    k: float = 1.5,
) -> list[OutlierFlag]:
    """Marca (no elimina) las observaciones fuera de las cercas de Tukey.

    Las cercas se calculan con todas las observaciones juntas. Cada marca
    explica en español qué valor es, dónde está y contra qué límite se comparó.
    """
    x = flatten_subgroups(subgroups)
    low, high = tukey_fences(x, k)
    q1, q3 = np.percentile(x, [25, 75])
    flags: list[OutlierFlag] = []
    for i, g in enumerate(subgroups):
        name = str(labels[i]) if labels is not None else str(i + 1)
        for j, v in enumerate(np.asarray(g, dtype=float).ravel()):
            if v > high:
                side, limit, formula = "por encima", high, f"Q3 + {_g(k)}·IQR"
            elif v < low:
                side, limit, formula = "por debajo", low, f"Q1 - {_g(k)}·IQR"
            else:
                continue
            flags.append(
                OutlierFlag(
                    subgroup_index=i,
                    position=j,
                    value=float(v),
                    reason=(
                        f"El valor {_g(v)} del subgrupo {name} (posición {j + 1}) está {side} "
                        f"de la cerca de Tukey {formula} = {_g(limit)} "
                        f"(Q1 = {_g(q1)}, Q3 = {_g(q3)}, IQR = {_g(q3 - q1)}). "
                        "Se marca para revisión: solo debe excluirse si se documenta una causa asignable."
                    ),
                )
            )
    return flags


def summarize(
    subgroups: Sequence[Sequence[float]], labels: Optional[Sequence[str]] = None
) -> SummaryResult:
    """Resumen completo para `SummaryResponse`: subgrupos, descriptiva global,
    si el tamaño es constante y atípicos marcados con 1.5·IQR."""
    x = flatten_subgroups(subgroups)
    subs = summarize_subgroups(subgroups, labels)
    sizes = {s.n for s in subs}
    return SummaryResult(
        subgroups=subs,
        overall=describe(x),
        constant_size=len(sizes) == 1,
        outliers=flag_outliers_iqr(subgroups, labels),
    )


# --------------------------------------------------------------------------
# Histograma
# --------------------------------------------------------------------------


def sturges_bins(n: int) -> int:
    """k = ceil(log2 n) + 1 (regla de Sturges)."""
    return max(1, int(math.ceil(math.log2(max(n, 1)))) + 1)


def build_histogram(
    values: Sequence[float],
    bins: Optional[int] = None,
    extend_to: Sequence[Optional[float]] = (),
    curve_points: int = 101,
) -> Histogram:
    """Histograma de frecuencias y curva normal ajustada en la misma escala.

    La curva es f(x) = N · w · φ((x - x̄)/s) / s, con N observaciones y w el
    ancho de clase, de modo que el área bajo la curva coincide con el área de
    las barras (Montgomery, cap. 3). `extend_to` amplía el eje x de la curva
    para que incluya, por ejemplo, los límites de especificación.

    Si la dispersión es cero no hay curva normal: las listas van vacías.
    """
    x = as_clean_array(values)
    n = int(x.size)
    k = bins if bins is not None else sturges_bins(n)
    counts, edges = np.histogram(x, bins=k)
    mean = float(x.mean())
    s = float(x.std(ddof=1)) if n > 1 else 0.0
    curve_x: list[float] = []
    curve_y: list[float] = []
    if s > 0:
        width = float(edges[1] - edges[0])
        lo = min(float(edges[0]), mean - 3.5 * s)
        hi = max(float(edges[-1]), mean + 3.5 * s)
        for e in extend_to:
            if e is not None and math.isfinite(e):
                lo, hi = min(lo, float(e)), max(hi, float(e))
        xs = np.linspace(lo, hi, curve_points)
        ys = n * width * stats.norm.pdf(xs, loc=mean, scale=s)
        curve_x = [float(v) for v in xs]
        curve_y = [float(v) for v in ys]
    return Histogram(
        edges=[float(e) for e in edges],
        counts=[int(c) for c in counts],
        normal_curve_x=curve_x,
        normal_curve_y=curve_y,
    )


def _g(x: float, digits: int = 4) -> str:
    """Número con `digits` cifras significativas y coma decimal (mismo formato
    que `interpretation.fmt`)."""
    from .interpretation import fmt

    return fmt(x, digits)
