"""Gráficos de control por atributos: p, np, c y u.

Igual que en variables, primero se estima el parámetro del proceso (p̄, c̄ o ū)
con los subgrupos retenidos y después se construyen los límites a partir de él.

Fuentes (Montgomery, *Introduction to Statistical Quality Control*, cap. 7):
- p, sección 7.2.1: p̄ = ΣD_i / Σn_i; p̄ ± L·sqrt(p̄(1-p̄)/n_i).
  Con n variable (sección 7.2.2, enfoque de límites variables) los límites se
  calculan por punto con su n_i.
- np, sección 7.2.1: n·p̄ ± L·sqrt(n·p̄(1-p̄)); exige n constante.
- c, sección 7.3.1: c̄ ± L·sqrt(c̄), con c̄ el promedio de no conformidades por
  unidad de inspección (de tamaño constante).
- u, sección 7.3.1 y 7.3.2: ū = Σc_i / Σn_i; ū ± L·sqrt(ū/n_i), límites por
  punto cuando n_i varía; n_i puede ser fraccionario (unidades de inspección).
- El límite inferior negativo se trunca en 0 (las proporciones y conteos no son
  negativos) y en p el superior se trunca en 1.

Simetría: las zonas A/B/C solo se usan si ningún límite quedó truncado. Si en
algún punto el límite se truncó, las reglas de zonas se omiten en todo el panel.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Optional, Sequence

import numpy as np

from .constants import SPCInputError
from .rules import ControlLimits

ATTRIBUTES_CHARTS = ("p", "np", "c", "u")
CENTER_PARAM = {"p": "p_bar", "np": "p_bar", "c": "c_bar", "u": "u_bar"}
_INT_TOL = 1e-9


@dataclass(frozen=True)
class AttributeEstimate:
    """Parámetro estimado en Fase I (p̄, c̄ o ū) y datos de trazabilidad."""

    chart_type: str
    value: float
    subgroup_size: Optional[float]  # n constante usado; None si fue variable (o en c)
    points_used: int
    total_count: float
    total_size: float
    warnings: list[str] = field(default_factory=list)

    @property
    def params(self) -> dict[str, float]:
        return {CENTER_PARAM[self.chart_type]: self.value}


@dataclass(frozen=True)
class Recommendation:
    chart_type: str
    alternatives: list[str]
    justification: str


# --------------------------------------------------------------------------
# Validación
# --------------------------------------------------------------------------


def _check_type(chart_type: str) -> str:
    if chart_type not in ATTRIBUTES_CHARTS:
        raise SPCInputError(f"Tipo de gráfico por atributos desconocido: {chart_type!r}.")
    return chart_type


def validate_attribute_data(chart_type: str, counts: Sequence[float], sizes: Optional[Sequence[float]]
                            ) -> tuple[np.ndarray, Optional[np.ndarray]]:
    """Valida conteos y tamaños. Devuelve (counts, sizes) como arreglos.

    - p, np y u exigen `sizes`; np además lo exige constante.
    - c no necesita `sizes`; si llega y no es constante, se rechaza (use u).
    - Conteos enteros y no negativos; en p y np, D_i <= n_i.
    """
    _check_type(chart_type)
    try:
        c = np.asarray(counts, dtype=float).ravel()
    except (TypeError, ValueError) as exc:
        raise SPCInputError("Los conteos deben ser numéricos.") from exc
    if c.shape[0] < 2:
        raise SPCInputError("Se necesitan al menos 2 subgrupos.", "insufficient_data")
    if not np.all(np.isfinite(c)):
        raise SPCInputError("Los conteos contienen valores vacíos, NaN o infinitos.")
    if np.any(c < 0):
        raise SPCInputError("Los conteos no pueden ser negativos.")
    if np.any(np.abs(c - np.round(c)) > _INT_TOL):
        raise SPCInputError("Los conteos deben ser números enteros (unidades no conformes o no conformidades).")
    c = np.round(c)

    s: Optional[np.ndarray] = None
    if sizes is not None:
        try:
            s = np.asarray(sizes, dtype=float).ravel()
        except (TypeError, ValueError) as exc:
            raise SPCInputError("Los tamaños de muestra deben ser numéricos.") from exc
        if s.shape != c.shape:
            raise SPCInputError("Debe haber un tamaño de muestra por cada conteo.")
        if not np.all(np.isfinite(s)) or np.any(s <= 0):
            raise SPCInputError("Los tamaños de muestra deben ser positivos.")

    if chart_type in ("p", "np", "u") and s is None:
        raise SPCInputError(f"El gráfico {chart_type} necesita el tamaño de muestra de cada subgrupo.")
    if chart_type in ("p", "np"):
        if np.any(np.abs(s - np.round(s)) > _INT_TOL):
            raise SPCInputError("En p y np el tamaño de muestra es un número entero de unidades.")
        if np.any(c > s):
            raise SPCInputError("El número de unidades no conformes no puede superar el tamaño de muestra.")
    if chart_type == "np" and not _is_constant(s):
        raise SPCInputError("El gráfico np exige tamaño de muestra constante. Con tamaño variable use el gráfico p.")
    if chart_type == "c" and s is not None and not _is_constant(s):
        raise SPCInputError("El gráfico c supone una unidad de inspección de tamaño constante. "
                            "Con tamaño variable use el gráfico u.")
    return c, s


def _is_constant(s: np.ndarray) -> bool:
    return bool(np.all(np.abs(s - s[0]) <= _INT_TOL * max(1.0, abs(s[0]))))


def _keep(m: int, excluded: Iterable[int]) -> np.ndarray:
    keep = np.ones(m, dtype=bool)
    for i in excluded:
        i = int(i)
        if not 0 <= i < m:
            raise SPCInputError(f"El índice excluido {i} está fuera de rango (0 a {m - 1}).")
        keep[i] = False
    if keep.sum() < 2:
        k = int(keep.sum())
        left = "Queda 1 subgrupo" if k == 1 else f"Quedan {k} subgrupos"
        raise SPCInputError(f"{left} después de las exclusiones; se necesitan "
                            "al menos 2 para estimar los límites.", "insufficient_data")
    return keep


def _common_warnings(used: int) -> list[str]:
    if used < 20:
        return [f"Los límites se estimaron con {used} subgrupos. Montgomery (capítulo 7) recomienda "
                "al menos 20 a 25 subgrupos en Fase I."]
    return []


# --------------------------------------------------------------------------
# Estimación (Fase I)
# --------------------------------------------------------------------------


def estimate_p(counts, sizes, excluded: Iterable[int] = (), chart_type: str = "p") -> AttributeEstimate:
    """p̄ = ΣD_i / Σn_i sobre los subgrupos retenidos (Montgomery, sección 7.2.1).

    Con n variable es el promedio ponderado por n_i, no el promedio de los p_i.
    """
    c, s = validate_attribute_data(chart_type, counts, sizes)
    keep = _keep(c.shape[0], excluded)
    total_d, total_n = float(c[keep].sum()), float(s[keep].sum())
    p_bar = total_d / total_n
    size = float(s[0]) if _is_constant(s) else None
    warnings = _common_warnings(int(keep.sum()))
    if p_bar == 0.0:
        warnings.append("No se observó ninguna unidad no conforme: p̄ = 0 y los límites colapsan en 0. "
                        "El gráfico no puede detectar aumentos hasta que se acumulen datos con defectuosos.")
    elif p_bar == 1.0:
        warnings.append("Todas las unidades fueron no conformes: p̄ = 1 y los límites colapsan en 1.")
    return AttributeEstimate(chart_type, p_bar, size, int(keep.sum()), total_d, total_n, warnings)


def estimate_np(counts, sizes, excluded: Iterable[int] = ()) -> AttributeEstimate:
    """Mismo p̄ que el gráfico p; el gráfico np grafica D_i con n constante."""
    return estimate_p(counts, sizes, excluded, chart_type="np")


def estimate_c(counts, sizes=None, excluded: Iterable[int] = ()) -> AttributeEstimate:
    """c̄ = promedio de no conformidades por unidad de inspección (Montgomery, sección 7.3.1)."""
    c, _ = validate_attribute_data("c", counts, sizes)
    keep = _keep(c.shape[0], excluded)
    c_bar = float(c[keep].mean())
    warnings = _common_warnings(int(keep.sum()))
    if c_bar == 0.0:
        warnings.append("No se observó ninguna no conformidad: c̄ = 0 y los límites colapsan en 0.")
    return AttributeEstimate("c", c_bar, None, int(keep.sum()), float(c[keep].sum()), float(keep.sum()), warnings)


def estimate_u(counts, sizes, excluded: Iterable[int] = ()) -> AttributeEstimate:
    """ū = Σc_i / Σn_i sobre los subgrupos retenidos (Montgomery, sección 7.3.1)."""
    c, s = validate_attribute_data("u", counts, sizes)
    keep = _keep(c.shape[0], excluded)
    total_c, total_n = float(c[keep].sum()), float(s[keep].sum())
    u_bar = total_c / total_n
    warnings = _common_warnings(int(keep.sum()))
    if u_bar == 0.0:
        warnings.append("No se observó ninguna no conformidad: ū = 0 y los límites colapsan en 0.")
    size = float(s[0]) if _is_constant(s) else None
    return AttributeEstimate("u", u_bar, size, int(keep.sum()), total_c, total_n, warnings)


def estimate(chart_type: str, counts, sizes=None, excluded: Iterable[int] = ()) -> AttributeEstimate:
    _check_type(chart_type)
    if chart_type == "p":
        return estimate_p(counts, sizes, excluded)
    if chart_type == "np":
        return estimate_np(counts, sizes, excluded)
    if chart_type == "c":
        return estimate_c(counts, sizes, excluded)
    return estimate_u(counts, sizes, excluded)


# --------------------------------------------------------------------------
# Límites a partir del parámetro
# --------------------------------------------------------------------------


def _truncated_limits(center: np.ndarray, sd: np.ndarray, L: float, upper_cap: Optional[np.ndarray]
                      ) -> tuple[ControlLimits, bool, bool]:
    raw_u = center + L * sd
    raw_l = center - L * sd
    lcl = np.maximum(raw_l, 0.0)
    lower_cut = bool(np.any(raw_l < 0.0))
    upper_cut = False
    ucl = raw_u
    if upper_cap is not None:
        upper_cut = bool(np.any(raw_u > upper_cap))
        ucl = np.minimum(raw_u, upper_cap)
    symmetric = not (lower_cut or upper_cut)
    lim = ControlLimits(center=center, ucl=ucl, lcl=lcl, sigma=sd, symmetric=symmetric, limit_width=float(L),
                        discrete=True)
    return lim, lower_cut, upper_cut


def _check_param(value: float, name: str, upper: Optional[float] = None) -> None:
    if not math.isfinite(value) or value < 0 or (upper is not None and value > upper):
        raise SPCInputError(f"Parámetro {name} inválido: {value!r}.")


def p_limits(p_bar: float, sizes, L: float = 3.0) -> ControlLimits:
    """p̄ ± L·sqrt(p̄(1-p̄)/n_i), por punto; LCI truncado en 0 y LCS en 1."""
    _check_param(p_bar, "p_bar", 1.0)
    n = np.asarray(sizes, dtype=float).ravel()
    center = np.full(n.shape, p_bar)
    sd = np.sqrt(p_bar * (1.0 - p_bar) / n)
    return _truncated_limits(center, sd, L, np.ones(n.shape))[0]


def np_limits(p_bar: float, n: float, m: int, L: float = 3.0) -> ControlLimits:
    """n·p̄ ± L·sqrt(n·p̄(1-p̄)); LCI truncado en 0 y LCS en n."""
    _check_param(p_bar, "p_bar", 1.0)
    center = np.full(m, n * p_bar)
    sd = np.full(m, math.sqrt(n * p_bar * (1.0 - p_bar)))
    return _truncated_limits(center, sd, L, np.full(m, float(n)))[0]


def c_limits(c_bar: float, m: int, L: float = 3.0) -> ControlLimits:
    """c̄ ± L·sqrt(c̄); LCI truncado en 0."""
    _check_param(c_bar, "c_bar")
    center = np.full(m, c_bar)
    sd = np.full(m, math.sqrt(c_bar))
    return _truncated_limits(center, sd, L, None)[0]


def u_limits(u_bar: float, sizes, L: float = 3.0) -> ControlLimits:
    """ū ± L·sqrt(ū/n_i), por punto; LCI truncado en 0."""
    _check_param(u_bar, "u_bar")
    n = np.asarray(sizes, dtype=float).ravel()
    center = np.full(n.shape, u_bar)
    sd = np.sqrt(u_bar / n)
    return _truncated_limits(center, sd, L, None)[0]


def limits_from_params(chart_type: str, params: dict[str, float], counts: np.ndarray,
                       sizes: Optional[np.ndarray], L: float = 3.0) -> ControlLimits:
    """Límites del panel para los subgrupos dados, a partir del parámetro congelado."""
    _check_type(chart_type)
    key = CENTER_PARAM[chart_type]
    if key not in params:
        raise SPCInputError(f"Los límites congelados del gráfico {chart_type} deben traer {key}.", "missing_limits")
    value = float(params[key])
    m = counts.shape[0]
    if chart_type == "p":
        return p_limits(value, sizes, L)
    if chart_type == "np":
        return np_limits(value, float(sizes[0]), m, L)
    if chart_type == "c":
        return c_limits(value, m, L)
    return u_limits(value, sizes, L)


def plotted_values(chart_type: str, counts: np.ndarray, sizes: Optional[np.ndarray]) -> np.ndarray:
    """p_i = D_i/n_i, np_i = D_i, c_i y u_i = c_i/n_i."""
    _check_type(chart_type)
    if chart_type in ("p", "u"):
        return counts / sizes
    return counts.astype(float)


def truncation_warnings(chart_type: str, limits: ControlLimits) -> list[str]:
    """Advertencias de truncamiento para la interpretación."""
    out = []
    raw_l = limits.center - limits.limit_width * limits.sigma
    if np.any(raw_l < 0):
        k = int(np.sum(raw_l < 0))
        where = "1 punto" if k == 1 else f"{k} puntos"
        out.append(f"El límite inferior del gráfico {chart_type} es negativo en {where} y se truncó en 0: "
                   "el gráfico no puede señalar mejoras por debajo del límite y las reglas de zonas "
                   "(WE2, WE3, N5 a N8) no se aplican.")
    if chart_type in ("p", "np"):
        cap = 1.0 if chart_type == "p" else None
        raw_u = limits.center + limits.limit_width * limits.sigma
        if cap is not None and np.any(raw_u > cap):
            out.append("El límite superior del gráfico p supera 1 y se truncó en 1.")
    return out


# --------------------------------------------------------------------------
# Asistente de selección
# --------------------------------------------------------------------------


def recommend_chart(counting: str, constant_size: bool) -> Recommendation:
    """Sugiere el gráfico por atributos (Montgomery, cap. 7; guía de la sección 7.4).

    - defectives (unidades no conformes, binomial): np si n es constante, p si varía.
    - defects (no conformidades, Poisson): c si la unidad de inspección es constante, u si varía.
    """
    if counting not in ("defectives", "defects"):
        raise SPCInputError("counting debe ser 'defectives' (unidades no conformes) o 'defects' (no conformidades).")
    if counting == "defectives":
        if constant_size:
            return Recommendation("np", ["p"], (
                "Se cuentan unidades no conformes (cada unidad es conforme o no), así que el número de "
                "defectuosos sigue una distribución binomial. Con tamaño de muestra constante se recomienda "
                "el gráfico np: grafica directamente el número de unidades no conformes, que es más fácil "
                "de leer en planta. El gráfico p es equivalente y conviene si se quiere reportar la fracción "
                "no conforme o si el tamaño de muestra podría cambiar más adelante."))
        return Recommendation("p", [], (
            "Se cuentan unidades no conformes con tamaño de muestra variable. El número de defectuosos es "
            "binomial y solo la fracción no conforme p = D/n es comparable entre muestras de distinto "
            "tamaño, por eso se usa el gráfico p con límites calculados para el n de cada muestra. El "
            "gráfico np no es válido porque su línea central n·p̄ cambiaría con cada n."))
    if constant_size:
        return Recommendation("c", ["u"], (
            "Se cuentan no conformidades (defectos), y una misma unidad puede tener varias; el conteo sigue "
            "una distribución de Poisson. Con una unidad de inspección de tamaño constante se recomienda el "
            "gráfico c, que grafica el total de no conformidades por unidad de inspección. El gráfico u da "
            "el mismo resultado expresado por unidad."))
    return Recommendation("u", [], (
        "Se cuentan no conformidades con un tamaño de inspección variable. El conteo sigue una distribución "
        "de Poisson cuya media crece con el tamaño inspeccionado, así que se grafica la tasa u = c/n (no conformidades por unidad) con límites "
        "calculados para el n de cada muestra. El gráfico c no es válido porque supone un área de "
        "oportunidad constante."))


__all__ = [
    "ATTRIBUTES_CHARTS", "CENTER_PARAM", "AttributeEstimate", "Recommendation",
    "validate_attribute_data", "estimate_p", "estimate_np", "estimate_c", "estimate_u", "estimate",
    "p_limits", "np_limits", "c_limits", "u_limits", "limits_from_params", "plotted_values",
    "truncation_warnings", "recommend_chart",
]
