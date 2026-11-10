"""Fase I (límites de prueba, exclusiones, congelar) y Fase II (monitoreo).

Fuente: Montgomery, *Introduction to Statistical Quality Control*, sección 5.4
("Phase I and Phase II of Control Chart Application") y sección 6.2.1
(límites de prueba, revisión de límites tras eliminar puntos con causa
asignable).

Fase I
    1. Se estiman los parámetros del proceso SIN los puntos excluidos.
    2. Se construyen los límites a partir de esos parámetros.
    3. Se grafican TODOS los puntos; los excluidos se marcan y no participan en
       las reglas de corrida.
    4. Se devuelven los parámetros listos para congelar (`FrozenParameters`).

Fase II
    Los datos nuevos se comparan con los parámetros congelados. Nunca se
    recalculan. En variables, si el n nuevo difiere del de Fase I, los límites se
    reconstruyen con el n nuevo a partir de mu y sigma; en p y u los límites se
    calculan por punto con el n de cada muestra a partir de p̄ o ū.

Cada resultado se convierte sin pérdida en `ChartResponse` del contrato con
`ChartResult.to_contract()` (falta solo `interpretation`, que arma
`interpretation.py` a partir de este resultado y de `warnings`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Optional, Sequence

import numpy as np

from . import attributes as attr
from . import variables as var
from .constants import SPCInputError
from .rules import ControlLimits, RuleOutcome, Violation, evaluate_limits

CHART_TYPES = var.VARIABLES_CHARTS + attr.ATTRIBUTES_CHARTS

PANEL_TITLES = {
    "xbar": "Gráfico X-barra (medias de subgrupo)",
    "r": "Gráfico R (rangos de subgrupo)",
    "s": "Gráfico S (desviaciones estándar de subgrupo)",
    "i": "Gráfico de individuales (I)",
    "mr": "Gráfico de rangos móviles (MR)",
    "p": "Gráfico p (fracción no conforme)",
    "np": "Gráfico np (número de unidades no conformes)",
    "c": "Gráfico c (no conformidades por unidad de inspección)",
    "u": "Gráfico u (no conformidades por unidad)",
}
PANELS = {"xbar_r": ("xbar", "r"), "xbar_s": ("xbar", "s"), "i_mr": ("i", "mr"),
          "p": ("p",), "np": ("np",), "c": ("c",), "u": ("u",)}


# --------------------------------------------------------------------------
# Estructuras de salida
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Exclusion:
    """Punto retirado del cálculo en Fase I. Equivale a `ExcludedPoint`."""

    index: int
    cause: str
    label: Optional[str] = None

    def to_contract(self) -> dict[str, Any]:
        return {"index": self.index, "label": self.label, "cause": self.cause}


@dataclass
class FrozenParameters:
    """Parámetros congelados de Fase I. Equivale a `FrozenLimits`."""

    chart_type: str
    subgroup_size: Optional[int]
    sigma_method: Optional[str]
    params: dict[str, float]
    points_used: int
    excluded: list[Exclusion] = field(default_factory=list)
    limit_width: float = 3.0

    def to_contract(self) -> dict[str, Any]:
        return {
            "chart_type": self.chart_type,
            "subgroup_size": self.subgroup_size,
            "sigma_method": self.sigma_method,
            "params": dict(self.params),
            "points_used": self.points_used,
            "excluded": [e.to_contract() for e in self.excluded],
            "limit_width": self.limit_width,
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "FrozenParameters":
        """Acepta el dict de `FrozenLimits.model_dump()` o un objeto con esos atributos."""
        get = (lambda k, d=None: data.get(k, d)) if isinstance(data, Mapping) else (
            lambda k, d=None: getattr(data, k, d))
        excl = []
        for e in get("excluded", []) or []:
            excl.append(_to_exclusion(e))
        size = get("subgroup_size")
        return cls(
            chart_type=get("chart_type"),
            subgroup_size=None if size is None else int(size),
            sigma_method=get("sigma_method"),
            params={k: float(v) for k, v in dict(get("params", {}) or {}).items()},
            points_used=int(get("points_used", 0) or 0),
            excluded=excl,
            limit_width=float(get("limit_width", 3.0) or 3.0),
        )


@dataclass
class Panel:
    """Un panel graficado. `to_contract()` da exactamente los campos de `ChartSeries`.

    `indices[k]` es el subgrupo al que corresponde `values[k]` (en MR, k + 1).
    `rules_skipped` asocia cada regla omitida con el motivo.
    """

    name: str
    title: str
    labels: list[str]
    values: list[float]
    center: list[float]
    ucl: list[float]
    lcl: list[float]
    violations: list[Violation]
    excluded: list[int]
    indices: list[int]
    symmetric: bool
    rules_applied: list[str]
    rules_skipped: dict[str, str]

    def to_contract(self) -> dict[str, Any]:
        return {
            "name": self.name, "title": self.title, "labels": list(self.labels),
            "values": list(self.values), "center": list(self.center),
            "ucl": list(self.ucl), "lcl": list(self.lcl),
            "violations": [{"rule": v.rule, "index": v.index, "description": v.description}
                           for v in self.violations],
            "excluded": list(self.excluded),
            "indices": list(self.indices),
            "rules_applied": list(self.rules_applied),
            "rules_skipped": [{"rule": r, "reason": m} for r, m in self.rules_skipped.items()],
        }


@dataclass
class ChartResult:
    """Resultado completo de un gráfico en Fase I o II."""

    chart_type: str
    phase: str
    charts: list[Panel]
    limits: FrozenParameters
    in_control: bool
    out_of_control_points: list[int]
    warnings: list[str] = field(default_factory=list)

    def to_contract(self) -> dict[str, Any]:
        """Campos de `ChartResponse` salvo `interpretation`."""
        return {
            "chart_type": self.chart_type,
            "phase": self.phase,
            "charts": [p.to_contract() for p in self.charts],
            "limits": self.limits.to_contract(),
            "in_control": self.in_control,
            "out_of_control_points": list(self.out_of_control_points),
        }


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------


def _to_exclusion(e: Any) -> Exclusion:
    if isinstance(e, Exclusion):
        return e
    if isinstance(e, Mapping):
        index, cause, label = e.get("index"), e.get("cause"), e.get("label")
    elif isinstance(e, (tuple, list)):
        index, cause = e[0], e[1] if len(e) > 1 else None
        label = e[2] if len(e) > 2 else None
    else:
        index, cause, label = getattr(e, "index", None), getattr(e, "cause", None), getattr(e, "label", None)
    if index is None or isinstance(index, bool) or int(index) != index:
        raise SPCInputError("Cada punto excluido necesita un índice entero.")
    if cause is None or not str(cause).strip():
        raise SPCInputError(f"El punto excluido {index} necesita una causa asignable documentada.")
    return Exclusion(index=int(index), cause=str(cause).strip(), label=label)


def _normalize_exclusions(excluded: Iterable[Any], m: int) -> list[Exclusion]:
    out: list[Exclusion] = []
    seen: set[int] = set()
    for e in excluded or ():
        ex = _to_exclusion(e)
        if not 0 <= ex.index < m:
            raise SPCInputError(f"El índice excluido {ex.index} está fuera de rango (0 a {m - 1}).")
        if ex.index in seen:
            raise SPCInputError(f"El punto {ex.index} aparece excluido más de una vez.")
        seen.add(ex.index)
        out.append(ex)
    return sorted(out, key=lambda e: e.index)


def _labels(labels: Optional[Sequence[str]], m: int) -> list[str]:
    if labels is None:
        return [str(i + 1) for i in range(m)]
    if len(labels) != m:
        raise SPCInputError(f"Se recibieron {len(labels)} etiquetas para {m} subgrupos.")
    return [str(x) for x in labels]


def _clean(a: np.ndarray) -> list[float]:
    """Lista de floats; nunca NaN ni infinito (rule 7 de CLAUDE.md)."""
    a = np.asarray(a, dtype=float)
    if not np.all(np.isfinite(a)):
        raise SPCInputError("Se produjo un valor no finito al construir el gráfico.")
    return [float(v) for v in a]


def _build_panel(name: str, values: np.ndarray, limits: ControlLimits, indices: np.ndarray,
                 labels: list[str], excluded_pos: list[int], rules: Iterable[str]) -> Panel:
    m = values.shape[0]
    c, u, lo, _ = limits.as_arrays(m)
    lab = [labels[i] for i in indices]
    outcome: RuleOutcome = evaluate_limits(values, limits, list(rules), excluded=excluded_pos,
                                           labels=lab, indices=[int(i) for i in indices])
    return Panel(
        name=name, title=PANEL_TITLES[name], labels=lab, values=_clean(values),
        center=_clean(c), ucl=_clean(u), lcl=_clean(lo), violations=outcome.violations,
        excluded=sorted(int(indices[p]) for p in excluded_pos), indices=[int(i) for i in indices],
        symmetric=limits.symmetric, rules_applied=outcome.applied, rules_skipped=outcome.skipped,
    )


def _rule_ids(rules: Any) -> list[str]:
    if rules is None:
        return ["WE1"]
    if isinstance(rules, Mapping):
        rules = rules.get("enabled", ["WE1"])
    elif hasattr(rules, "enabled"):
        rules = rules.enabled
    return list(rules)


def _finish(chart_type: str, phase: str, panels: list[Panel], frozen: FrozenParameters,
            warnings: list[str]) -> ChartResult:
    flagged = sorted({v.index for p in panels for v in p.violations})
    for p in panels:
        for rid, msg in p.rules_skipped.items():
            text = f"Panel {p.name.upper()}: {msg}"
            if text not in warnings:
                warnings.append(text)
    return ChartResult(chart_type=chart_type, phase=phase, charts=panels, limits=frozen,
                       in_control=not flagged, out_of_control_points=flagged, warnings=warnings)


def _sigma_zero_warning(sigma: float) -> list[str]:
    if sigma == 0.0:
        return ["La dispersión estimada es 0 (todos los valores retenidos son iguales): los límites colapsan "
                "en la línea central y cualquier valor distinto será señal. Revise la resolución del "
                "instrumento de medición antes de usar estos límites."]
    return []


# --------------------------------------------------------------------------
# Variables
# --------------------------------------------------------------------------


def _variables_panels(chart_type: str, x: np.ndarray, mu: float, sigma: float, n: int, L: float,
                      excluded_idx: list[int], labels: list[str], rules: list[str]) -> list[Panel]:
    loc_lim, disp_lim = var.limits_from_params(chart_type, mu, sigma, n, L)
    loc, disp, disp_idx = var.plotted_statistics(chart_type, x)
    m = x.shape[0]
    excl = set(excluded_idx)
    loc_excl = sorted(excl)
    if chart_type == "i_mr":
        # MR_i (posición k, subgrupo k+1) queda fuera si el punto i o el i-1 está excluido.
        disp_excl = [k for k in range(m - 1) if (k + 1) in excl or k in excl]
    else:
        disp_excl = loc_excl
    names = PANELS[chart_type]
    return [
        _build_panel(names[0], loc, loc_lim, np.arange(m), labels, loc_excl, rules),
        _build_panel(names[1], disp, disp_lim, disp_idx, labels, disp_excl, rules),
    ]


def variables_phase_one(chart_type: str, subgroups, *, excluded: Iterable[Any] = (),
                        limit_width: float = 3.0, rules: Any = ("WE1",),
                        labels: Optional[Sequence[str]] = None) -> ChartResult:
    """Fase I de X-barra-R, X-barra-S o I-MR.

    Estima mu y sigma sin los excluidos, construye los límites con ancho L y
    grafica todos los subgrupos marcando los excluidos.
    """
    x = var.as_matrix(subgroups, chart_type)
    m = x.shape[0]
    excl = _normalize_exclusions(excluded, m)
    idx = [e.index for e in excl]
    if not (math.isfinite(limit_width) and limit_width > 0):
        raise SPCInputError("El ancho de los límites L debe ser positivo.")
    est = var.estimate(chart_type, x, idx)
    lab = _labels(labels, m)
    panels = _variables_panels(chart_type, x, est.mu, est.sigma, est.subgroup_size, limit_width,
                               idx, lab, _rule_ids(rules))
    frozen = FrozenParameters(
        chart_type=chart_type, subgroup_size=est.subgroup_size, sigma_method=est.sigma_method,
        params=est.params, points_used=est.points_used, excluded=excl, limit_width=float(limit_width),
    )
    warnings = list(est.warnings) + _sigma_zero_warning(est.sigma)
    return _finish(chart_type, "I", panels, frozen, warnings)


def variables_phase_two(chart_type: str, subgroups, frozen: Any, *, rules: Any = ("WE1",),
                        labels: Optional[Sequence[str]] = None) -> ChartResult:
    """Fase II: compara datos nuevos con (mu, sigma) congelados. Nunca recalcula.

    Si el n nuevo difiere del de Fase I, los límites se reconstruyen con el n
    nuevo a partir de mu y sigma (Montgomery, sección 6.2.1, límites con
    parámetros conocidos).
    """
    fz = _require_frozen(frozen, chart_type)
    for key in ("mu", "sigma"):
        if key not in fz.params:
            raise SPCInputError(f"Los límites congelados deben traer {key}.", "missing_limits")
    mu, sigma = fz.params["mu"], fz.params["sigma"]
    x = var.as_matrix(subgroups, chart_type)
    n = x.shape[1]
    warnings: list[str] = []
    if chart_type != "i_mr" and fz.subgroup_size is not None and n != fz.subgroup_size:
        warnings.append(f"Los subgrupos nuevos tienen n = {n} y los de Fase I n = {fz.subgroup_size}: "
                        "los límites se reconstruyeron con el n nuevo a partir de mu y sigma congelados.")
    lab = _labels(labels, x.shape[0])
    panels = _variables_panels(chart_type, x, mu, sigma, n, fz.limit_width, [], lab, _rule_ids(rules))
    warnings += _sigma_zero_warning(sigma)
    return _finish(chart_type, "II", panels, fz, warnings)


# --------------------------------------------------------------------------
# Atributos
# --------------------------------------------------------------------------


def _attributes_panel(chart_type: str, counts: np.ndarray, sizes: Optional[np.ndarray],
                      params: dict[str, float], L: float, excluded_idx: list[int],
                      labels: list[str], rules: list[str]) -> tuple[Panel, ControlLimits]:
    lim = attr.limits_from_params(chart_type, params, counts, sizes, L)
    values = attr.plotted_values(chart_type, counts, sizes)
    panel = _build_panel(chart_type, values, lim, np.arange(counts.shape[0]), labels,
                         sorted(excluded_idx), rules)
    return panel, lim


def attributes_phase_one(chart_type: str, counts, sizes=None, *, excluded: Iterable[Any] = (),
                         limit_width: float = 3.0, rules: Any = ("WE1",),
                         labels: Optional[Sequence[str]] = None) -> ChartResult:
    """Fase I de p, np, c o u. Estima p̄, c̄ o ū sin los excluidos."""
    c, s = attr.validate_attribute_data(chart_type, counts, sizes)
    m = c.shape[0]
    excl = _normalize_exclusions(excluded, m)
    idx = [e.index for e in excl]
    if not (math.isfinite(limit_width) and limit_width > 0):
        raise SPCInputError("El ancho de los límites L debe ser positivo.")
    est = attr.estimate(chart_type, c, s, idx)
    lab = _labels(labels, m)
    panel, lim = _attributes_panel(chart_type, c, s, est.params, limit_width, idx, lab, _rule_ids(rules))
    size = None if est.subgroup_size is None else _int_if_whole(est.subgroup_size)
    frozen = FrozenParameters(chart_type=chart_type, subgroup_size=size, sigma_method=None,
                              params=est.params, points_used=est.points_used, excluded=excl,
                              limit_width=float(limit_width))
    warnings = list(est.warnings) + attr.truncation_warnings(chart_type, lim)
    return _finish(chart_type, "I", [panel], frozen, warnings)


def attributes_phase_two(chart_type: str, counts, sizes, frozen: Any, *, rules: Any = ("WE1",),
                         labels: Optional[Sequence[str]] = None) -> ChartResult:
    """Fase II de p, np, c o u contra el parámetro congelado. Nunca recalcula."""
    fz = _require_frozen(frozen, chart_type)
    c, s = attr.validate_attribute_data(chart_type, counts, sizes)
    warnings: list[str] = []
    if chart_type == "np" and fz.subgroup_size is not None and float(s[0]) != float(fz.subgroup_size):
        warnings.append(f"Las muestras nuevas tienen n = {_int_if_whole(float(s[0]))} y las de Fase I "
                        f"n = {fz.subgroup_size}: los límites np se reconstruyeron con el n nuevo a partir de p̄.")
    lab = _labels(labels, c.shape[0])
    panel, lim = _attributes_panel(chart_type, c, s, fz.params, fz.limit_width, [], lab, _rule_ids(rules))
    warnings += attr.truncation_warnings(chart_type, lim)
    return _finish(chart_type, "II", [panel], fz, warnings)


def _int_if_whole(v: float) -> Optional[int]:
    """`FrozenLimits.subgroup_size` es entero; un n fraccionario de u se guarda como None."""
    return int(round(v)) if abs(v - round(v)) < 1e-9 else None


def _require_frozen(frozen: Any, chart_type: str) -> FrozenParameters:
    if frozen is None:
        raise SPCInputError("La Fase II necesita los límites congelados de la Fase I.", "missing_limits")
    fz = frozen if isinstance(frozen, FrozenParameters) else FrozenParameters.from_mapping(frozen)
    if fz.chart_type != chart_type:
        raise SPCInputError(f"Los límites congelados son de un gráfico {fz.chart_type} y se pidió {chart_type}.",
                            "missing_limits")
    if not (math.isfinite(fz.limit_width) and fz.limit_width > 0):
        raise SPCInputError("El ancho L de los límites congelados debe ser positivo.")
    return fz


# --------------------------------------------------------------------------
# Puntos de entrada únicos (los que usa el router)
# --------------------------------------------------------------------------


def phase_one(chart_type: str, data, sizes=None, **kwargs) -> ChartResult:
    """Fase I para cualquier gráfico. `data` son subgrupos (variables) o conteos (atributos)."""
    if chart_type in var.VARIABLES_CHARTS:
        if sizes is not None:
            raise SPCInputError("Los gráficos por variables no usan `sizes`.")
        return variables_phase_one(chart_type, data, **kwargs)
    if chart_type in attr.ATTRIBUTES_CHARTS:
        return attributes_phase_one(chart_type, data, sizes, **kwargs)
    raise SPCInputError(f"Tipo de gráfico desconocido: {chart_type!r}.")


def phase_two(chart_type: str, data, frozen: Any, sizes=None, **kwargs) -> ChartResult:
    """Fase II para cualquier gráfico, contra límites congelados."""
    if chart_type in var.VARIABLES_CHARTS:
        if sizes is not None:
            raise SPCInputError("Los gráficos por variables no usan `sizes`.")
        return variables_phase_two(chart_type, data, frozen, **kwargs)
    if chart_type in attr.ATTRIBUTES_CHARTS:
        return attributes_phase_two(chart_type, data, sizes, frozen, **kwargs)
    raise SPCInputError(f"Tipo de gráfico desconocido: {chart_type!r}.")


__all__ = [
    "CHART_TYPES", "PANEL_TITLES", "PANELS", "Exclusion", "FrozenParameters", "Panel", "ChartResult",
    "variables_phase_one", "variables_phase_two", "attributes_phase_one", "attributes_phase_two",
    "phase_one", "phase_two",
]
