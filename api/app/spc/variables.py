"""Gráficos de control por variables: X-barra-R, X-barra-S e I-MR.

Cada gráfico se construye en dos pasos separados:

1. `estimate_*`: estima los parámetros del proceso (mu y sigma) con los
   subgrupos que no están excluidos.
2. `*_limits`: construye los límites de los dos paneles a partir de (mu, sigma,
   n, L). Es lo que permite congelar (mu, sigma) en Fase I y reconstruir los
   límites en Fase II con otro n.

Fuentes (Montgomery, *Introduction to Statistical Quality Control*, cap. 6):
- X-barra y R, sección 6.2.1: x̿ ± A2·R̄; LCS_R = D4·R̄, LCI_R = D3·R̄;
  sigma = R̄/d2 (ec. 6.6).
- X-barra y S, sección 6.3.1: x̿ ± A3·S̄; LCS_S = B4·S̄, LCI_S = B3·S̄;
  sigma = S̄/c4.
- Individuales y rango móvil, sección 6.4: x̄ ± 3·MR̄/d2; LCS_MR = D4·MR̄,
  LCI_MR = D3·MR̄ = 0, con d2 = 1.128 (n = 2) y MR_i = |x_i - x_{i-1}|.
- Límites con parámetros conocidos (forma general con ancho L, sección 6.2.1
  y apéndice VI): X-barra: mu ± L·sigma/sqrt(n); R: (d2 ± L·d3)·sigma;
  S: (c4 ± L·sqrt(1 - c4²))·sigma. Con mu = x̿ y sigma = R̄/d2 (o S̄/c4)
  estas fórmulas son idénticas a las de A2, D3, D4, A3, B3 y B4.

Python puro: sin Pydantic, sin disco ni red.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Sequence

import numpy as np

from .constants import MAX_N_RANGE, SPCInputError, c4, d2, d3
from .rules import ControlLimits

VARIABLES_CHARTS = ("xbar_r", "xbar_s", "i_mr")
SIGMA_METHOD = {"xbar_r": "rbar_d2", "xbar_s": "sbar_c4", "i_mr": "mrbar_d2"}
DISPERSION_PARAM = {"xbar_r": "r_bar", "xbar_s": "s_bar", "i_mr": "mr_bar"}


@dataclass(frozen=True)
class SubgroupStats:
    """Estadísticos por subgrupo (o por observación en I-MR)."""

    n: int
    means: np.ndarray
    ranges: np.ndarray
    stds: np.ndarray


@dataclass(frozen=True)
class ProcessEstimate:
    """Parámetros del proceso estimados en Fase I.

    `sigma` es la desviación estándar del PROCESO (no del estadístico).
    `dispersion_bar` es R̄, S̄ o MR̄ según el gráfico; se guarda para trazabilidad.
    """

    chart_type: str
    mu: float
    sigma: float
    subgroup_size: int
    sigma_method: str
    points_used: int
    dispersion_bar: float
    warnings: list[str] = field(default_factory=list)

    @property
    def params(self) -> dict[str, float]:
        return {"mu": self.mu, "sigma": self.sigma, DISPERSION_PARAM[self.chart_type]: self.dispersion_bar}


# --------------------------------------------------------------------------
# Validación y estadísticos
# --------------------------------------------------------------------------


def as_matrix(subgroups: Sequence[Sequence[float]] | Sequence[float], chart_type: str) -> np.ndarray:
    """Convierte la entrada en una matriz (m subgrupos × n) y la valida.

    - xbar_r y xbar_s: n >= 2 y constante.
    - i_mr: n = 1; acepta lista plana o lista de listas de un elemento.
    """
    if chart_type not in VARIABLES_CHARTS:
        raise SPCInputError(f"Tipo de gráfico por variables desconocido: {chart_type!r}.")
    if chart_type == "i_mr" and len(subgroups) > 0 and not isinstance(subgroups[0], (list, tuple, np.ndarray)):
        rows = [[v] for v in subgroups]
    else:
        rows = [list(r) for r in subgroups]
    if len(rows) < 2:
        raise SPCInputError("Se necesitan al menos 2 subgrupos.", "insufficient_data")
    sizes = {len(r) for r in rows}
    if len(sizes) != 1:
        raise SPCInputError(
            "Todos los subgrupos deben tener el mismo tamaño; se encontraron tamaños "
            f"{sorted(sizes)}. Revise los datos faltantes o use subgrupos de tamaño fijo."
        )
    n = sizes.pop()
    if chart_type == "i_mr" and n != 1:
        raise SPCInputError(f"El gráfico I-MR usa observaciones individuales (n = 1); se recibió n = {n}.")
    if chart_type in ("xbar_r", "xbar_s") and n < 2:
        raise SPCInputError("Los gráficos X-barra-R y X-barra-S necesitan subgrupos de tamaño n >= 2. "
                            "Para observaciones individuales use I-MR.")
    if chart_type == "xbar_r" and n > MAX_N_RANGE:
        raise SPCInputError(f"El gráfico R está tabulado hasta n = {MAX_N_RANGE}; con n = {n} use X-barra-S.")
    try:
        x = np.asarray(rows, dtype=float)
    except (TypeError, ValueError) as exc:
        raise SPCInputError("Los datos deben ser numéricos.") from exc
    if not np.all(np.isfinite(x)):
        raise SPCInputError("Los datos contienen valores vacíos, NaN o infinitos.")
    return x


def subgroup_statistics(x: np.ndarray) -> SubgroupStats:
    """Media, rango y desviación estándar muestral (ddof = 1) de cada subgrupo."""
    n = x.shape[1]
    means = x.mean(axis=1)
    ranges = x.max(axis=1) - x.min(axis=1)
    stds = x.std(axis=1, ddof=1) if n > 1 else np.zeros(x.shape[0])
    return SubgroupStats(n=n, means=means, ranges=ranges, stds=stds)


def moving_ranges(values: Sequence[float]) -> np.ndarray:
    """MR_i = |x_i - x_{i-1}|, i = 1..m-1 (Montgomery, sección 6.4)."""
    v = np.asarray(values, dtype=float).ravel()
    return np.abs(np.diff(v))


def _retained_mask(m: int, excluded: Iterable[int]) -> np.ndarray:
    keep = np.ones(m, dtype=bool)
    for i in excluded:
        i = int(i)
        if not 0 <= i < m:
            raise SPCInputError(f"El índice excluido {i} está fuera de rango (0 a {m - 1}).")
        keep[i] = False
    return keep


def _check_retained(keep: np.ndarray, minimum: int = 2) -> None:
    if keep.sum() < minimum:
        raise SPCInputError(
            f"Quedan {int(keep.sum())} subgrupos después de las exclusiones; se necesitan al menos {minimum} "
            "para estimar los límites.", "insufficient_data")


def _small_sample_warning(used: int) -> list[str]:
    if used < 20:
        return [f"Los límites se estimaron con {used} subgrupos. Montgomery (sección 6.2) recomienda "
                "al menos 20 a 25 para que los límites de prueba sean confiables."]
    return []


# --------------------------------------------------------------------------
# Estimación de parámetros (Fase I)
# --------------------------------------------------------------------------


def estimate_xbar_r(subgroups, excluded: Iterable[int] = ()) -> ProcessEstimate:
    """mu = x̿ y sigma = R̄/d2(n) con los subgrupos retenidos (Montgomery, ec. 6.6)."""
    x = as_matrix(subgroups, "xbar_r")
    st = subgroup_statistics(x)
    keep = _retained_mask(x.shape[0], excluded)
    _check_retained(keep)
    rbar = float(st.ranges[keep].mean())
    warnings = _small_sample_warning(int(keep.sum()))
    if st.n > 10:
        warnings.append(f"Con n = {st.n} el rango pierde eficiencia frente a S; Montgomery (sección 6.3) "
                        "recomienda X-barra-S para n mayor que 10.")
    return ProcessEstimate("xbar_r", float(st.means[keep].mean()), rbar / d2(st.n), st.n,
                           "rbar_d2", int(keep.sum()), rbar, warnings)


def estimate_xbar_s(subgroups, excluded: Iterable[int] = ()) -> ProcessEstimate:
    """mu = x̿ y sigma = S̄/c4(n) con los subgrupos retenidos (Montgomery, sección 6.3.1)."""
    x = as_matrix(subgroups, "xbar_s")
    st = subgroup_statistics(x)
    keep = _retained_mask(x.shape[0], excluded)
    _check_retained(keep)
    sbar = float(st.stds[keep].mean())
    return ProcessEstimate("xbar_s", float(st.means[keep].mean()), sbar / c4(st.n), st.n,
                           "sbar_c4", int(keep.sum()), sbar, _small_sample_warning(int(keep.sum())))


def estimate_i_mr(values, excluded: Iterable[int] = ()) -> ProcessEstimate:
    """mu = x̄ y sigma = MR̄/d2(2) con los puntos retenidos (Montgomery, sección 6.4).

    Un rango móvil MR_i = |x_i - x_{i-1}| entra en MR̄ solo si los dos puntos
    que lo forman están retenidos: excluir el punto i deja fuera MR_i y MR_{i+1}.
    No se forman rangos "saltando" sobre un excluido porque esos dos puntos no
    son consecutivos en el tiempo.
    """
    x = as_matrix(values, "i_mr")[:, 0]
    keep = _retained_mask(x.shape[0], excluded)
    _check_retained(keep)
    mr = moving_ranges(x)
    mr_keep = keep[1:] & keep[:-1]
    if not mr_keep.any():
        raise SPCInputError("No queda ningún par de observaciones consecutivas retenidas para calcular "
                            "el rango móvil.", "insufficient_data")
    mrbar = float(mr[mr_keep].mean())
    return ProcessEstimate("i_mr", float(x[keep].mean()), mrbar / d2(2), 1, "mrbar_d2",
                           int(keep.sum()), mrbar, _small_sample_warning(int(keep.sum())))


def estimate(chart_type: str, subgroups, excluded: Iterable[int] = ()) -> ProcessEstimate:
    """Despacha a `estimate_xbar_r`, `estimate_xbar_s` o `estimate_i_mr`."""
    return {"xbar_r": estimate_xbar_r, "xbar_s": estimate_xbar_s, "i_mr": estimate_i_mr}[
        _check_type(chart_type)](subgroups, excluded)


def _check_type(chart_type: str) -> str:
    if chart_type not in VARIABLES_CHARTS:
        raise SPCInputError(f"Tipo de gráfico por variables desconocido: {chart_type!r}.")
    return chart_type


# --------------------------------------------------------------------------
# Límites a partir de (mu, sigma, n, L)
# --------------------------------------------------------------------------


def _limits(center: float, ucl: float, lcl: float, sigma_stat: float, symmetric: bool, L: float) -> ControlLimits:
    return ControlLimits(center=np.array(float(center)), ucl=np.array(float(ucl)), lcl=np.array(float(lcl)),
                         sigma=np.array(float(sigma_stat)), symmetric=symmetric, limit_width=float(L))


def _check_params(mu: float, sigma: float, L: float) -> None:
    if not (math.isfinite(mu) and math.isfinite(sigma)) or sigma < 0:
        raise SPCInputError("mu debe ser finito y sigma finito y no negativo.")
    if not (math.isfinite(L) and L > 0):
        raise SPCInputError("El ancho de los límites L debe ser positivo.")


def xbar_limits(mu: float, sigma: float, n: int, L: float = 3.0) -> ControlLimits:
    """X-barra: mu ± L·sigma/sqrt(n) (Montgomery, sección 6.2.1)."""
    _check_params(mu, sigma, L)
    s = sigma / math.sqrt(n)
    return _limits(mu, mu + L * s, mu - L * s, s, True, L)


def r_limits(sigma: float, n: int, L: float = 3.0) -> ControlLimits:
    """R: LC = d2·sigma, LCS = (d2 + L·d3)·sigma, LCI = max(0, d2 - L·d3)·sigma.

    Equivale a D4·R̄ y D3·R̄ con R̄ = d2·sigma (Montgomery, sección 6.2.1).
    R es asimétrico: las zonas A/B/C no aplican.
    """
    _check_params(0.0, sigma, L)
    a, b = d2(n), d3(n)
    return _limits(a * sigma, (a + L * b) * sigma, max(0.0, (a - L * b) * sigma), b * sigma, False, L)


def s_limits(sigma: float, n: int, L: float = 3.0) -> ControlLimits:
    """S: LC = c4·sigma, límites (c4 ± L·sqrt(1-c4²))·sigma, LCI truncado en 0.

    Equivale a B4·S̄ y B3·S̄ con S̄ = c4·sigma (Montgomery, sección 6.3.1).
    """
    _check_params(0.0, sigma, L)
    c = c4(n)
    sd = math.sqrt(max(0.0, 1.0 - c * c)) * sigma
    return _limits(c * sigma, c * sigma + L * sd, max(0.0, c * sigma - L * sd), sd, False, L)


def individuals_limits(mu: float, sigma: float, L: float = 3.0) -> ControlLimits:
    """Individuales: mu ± L·sigma (Montgomery, sección 6.4)."""
    _check_params(mu, sigma, L)
    return _limits(mu, mu + L * sigma, mu - L * sigma, sigma, True, L)


def moving_range_limits(sigma: float, L: float = 3.0) -> ControlLimits:
    """MR (rango de 2): LC = d2(2)·sigma = MR̄, LCS = (d2 + L·d3)·sigma = D4·MR̄, LCI = 0."""
    return r_limits(sigma, 2, L)


def xbar_r_limits(mu: float, sigma: float, n: int, L: float = 3.0) -> tuple[ControlLimits, ControlLimits]:
    return xbar_limits(mu, sigma, n, L), r_limits(sigma, n, L)


def xbar_s_limits(mu: float, sigma: float, n: int, L: float = 3.0) -> tuple[ControlLimits, ControlLimits]:
    return xbar_limits(mu, sigma, n, L), s_limits(sigma, n, L)


def i_mr_limits(mu: float, sigma: float, L: float = 3.0) -> tuple[ControlLimits, ControlLimits]:
    return individuals_limits(mu, sigma, L), moving_range_limits(sigma, L)


def limits_from_params(chart_type: str, mu: float, sigma: float, n: int, L: float = 3.0
                       ) -> tuple[ControlLimits, ControlLimits]:
    """Límites de (localización, dispersión) para cualquier gráfico por variables."""
    _check_type(chart_type)
    if chart_type == "xbar_r":
        return xbar_r_limits(mu, sigma, n, L)
    if chart_type == "xbar_s":
        return xbar_s_limits(mu, sigma, n, L)
    return i_mr_limits(mu, sigma, L)


def plotted_statistics(chart_type: str, x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Valores de los dos paneles.

    Devuelve (localización, dispersión, índices_dispersión). En X-barra-R/S la
    dispersión tiene un valor por subgrupo; en I-MR tiene m-1 valores y
    `índices_dispersión` = 1..m-1 (MR_i corresponde al punto i).
    """
    _check_type(chart_type)
    if chart_type == "i_mr":
        v = x[:, 0]
        return v, moving_ranges(v), np.arange(1, v.shape[0])
    st = subgroup_statistics(x)
    disp = st.ranges if chart_type == "xbar_r" else st.stds
    return st.means, disp, np.arange(x.shape[0])


__all__ = [
    "VARIABLES_CHARTS", "SIGMA_METHOD", "DISPERSION_PARAM", "SubgroupStats", "ProcessEstimate",
    "as_matrix", "subgroup_statistics", "moving_ranges",
    "estimate_xbar_r", "estimate_xbar_s", "estimate_i_mr", "estimate",
    "xbar_limits", "r_limits", "s_limits", "individuals_limits", "moving_range_limits",
    "xbar_r_limits", "xbar_s_limits", "i_mr_limits", "limits_from_params", "plotted_statistics",
]
