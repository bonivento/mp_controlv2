"""Muestreo de aceptación por atributos: planes simples y dobles.

Fuente: Montgomery, *Introduction to Statistical Quality Control*, cap. 15
("Lot-by-Lot Acceptance Sampling for Attributes"):

- Plan simple (n, c): se inspeccionan n unidades y se acepta el lote si el
  número de defectuosas d cumple d <= c. Probabilidad de aceptación
  Pa(p) = P(d <= c), con d binomial (n, p) (curva OC tipo B), Poisson (n·p)
  o hipergeométrica (N, D = floor(p·N + 0.5), n) (curva OC tipo A, lote finito).
- Diseño por dos puntos de la curva OC: Pa(AQL) >= 1 - α (riesgo del
  productor) y Pa(LTPD) <= β (riesgo del consumidor).
- Inspección rectificadora: AOQ = Pa·p·(N - n)/N; sin N se usa AOQ ≈ Pa·p.
  AOQL = máximo de la curva AOQ. ATI = n + (1 - Pa)(N - n).
- Plan doble (n1, c1, r1, n2, c2): se acepta con la primera muestra si
  d1 <= c1, se rechaza si d1 >= r1; si no, se toma la segunda y se acepta si
  d1 + d2 <= c2. Montgomery usa r1 = c2 + 1.
      Pa^I  = P(d1 <= c1)
      Pa^II = Σ_{d=c1+1}^{r1-1} P(d1 = d)·P(d2 <= c2 - d)
      ASN   = n1 + n2·P(c1 < d1 < r1)          (sin inspección truncada)
      AOQ   = p·[Pa^I·(N - n1) + Pa^II·(N - n1 - n2)] / N
      ATI   = n1·Pa^I + (n1 + n2)·Pa^II + N·(1 - Pa)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal, Optional

import numpy as np
from scipy import optimize, stats

from .descriptive import CurvePoint
from .interpretation import (
    Interpretation,
    fmt,
    interpret_double_plan,
    interpret_single_plan,
)

Distribution = Literal["binomial", "poisson", "hypergeometric"]
_DISTRIBUTIONS = ("binomial", "poisson", "hypergeometric")


@dataclass
class SinglePlanResult:
    """Equivale a `SinglePlanResponse`."""

    n: int
    c: int
    distribution: str
    alpha_actual: Optional[float]
    beta_actual: Optional[float]
    oc_curve: list[CurvePoint]
    aoq_curve: list[CurvePoint]
    aoql: float
    aoql_at: float
    ati_curve: Optional[list[CurvePoint]]
    interpretation: Interpretation = field(default_factory=lambda: Interpretation(summary=""))


@dataclass
class DoublePlanResult:
    """Equivale a `DoublePlanResponse`."""

    oc_curve: list[CurvePoint]
    asn_curve: list[CurvePoint]
    first_sample_accept_curve: list[CurvePoint]
    alpha_actual: Optional[float]
    beta_actual: Optional[float]
    aoq_curve: list[CurvePoint]
    aoql: float
    ati_curve: Optional[list[CurvePoint]]
    interpretation: Interpretation = field(default_factory=lambda: Interpretation(summary=""))
    # Fracción defectuosa donde ocurre el AOQL.
    aoql_at: Optional[float] = None


@dataclass
class DesignSearch:
    """Detalle de la búsqueda del plan simple, para la interpretación.

    `previous` describe el mejor intento con c - 1: el menor n que cumple β y
    el α que tendría. Explica por qué no sirve un plan más pequeño (por
    ejemplo, el leído en un nomograma).
    """

    aql: float
    alpha: float
    ltpd: float
    beta: float
    n: int
    c: int
    previous_c: Optional[int] = None
    previous_n: Optional[int] = None
    previous_alpha: Optional[float] = None
    previous_beta: Optional[float] = None
    previous_feasible_beta: bool = False


# --------------------------------------------------------------------------
# Probabilidad de aceptación
# --------------------------------------------------------------------------


def _validate_distribution(distribution: str, lot_size: Optional[int], n: int) -> None:
    if distribution not in _DISTRIBUTIONS:
        raise ValueError(f"Distribución desconocida: {distribution!r}")
    if distribution == "hypergeometric" and lot_size is None:
        raise ValueError("La distribución hipergeométrica requiere el tamaño de lote N")
    if lot_size is not None and n > lot_size:
        raise ValueError(f"El tamaño de muestra n = {n} supera el tamaño de lote N = {lot_size}")


def defectives_in_lot(p, lot_size: int):
    """D = floor(p·N + 0.5): número de defectuosas en el lote para la hipergeométrica.

    Redondeo aritmético (0.5 hacia arriba). `np.rint` redondea 0.5 al par y,
    por la representación binaria, 0.07·50 = 3.5000000000000004 subía a 4
    mientras 0.05·50 = 2.5 bajaba a 2 (hallazgo H15). Antes de redondear se
    quita el ruido de coma flotante con 9 decimales.
    """
    x = np.round(np.asarray(p, dtype=float) * lot_size, 9)
    return np.floor(x + 0.5).astype(int)


def prob_accept(
    n,
    c,
    p,
    distribution: str = "binomial",
    lot_size: Optional[int] = None,
):
    """Pa(p) = P(d <= c) para un plan simple (Montgomery, cap. 15).

    Admite arreglos en `n`, `c` o `p` (difusión de numpy). Con la
    hipergeométrica, p se convierte en D = floor(p·N + 0.5) defectuosas del lote.
    """
    p = np.asarray(p, dtype=float)
    if distribution == "binomial":
        return stats.binom.cdf(c, n, p)
    if distribution == "poisson":
        return stats.poisson.cdf(c, np.asarray(n) * p)
    if distribution == "hypergeometric":
        if lot_size is None:
            raise ValueError("La distribución hipergeométrica requiere el tamaño de lote N")
        return stats.hypergeom.cdf(c, lot_size, defectives_in_lot(p, lot_size), n)
    raise ValueError(f"Distribución desconocida: {distribution!r}")


def _scalar_pa(n: int, c: int, p: float, distribution: str, lot_size: Optional[int]) -> float:
    return float(prob_accept(n, c, p, distribution, lot_size))


# --------------------------------------------------------------------------
# Diseño del plan simple
# --------------------------------------------------------------------------


def _min_n_for_beta(
    c: int, ltpd: float, beta: float, distribution: str, lot_size: Optional[int], max_n: int
) -> Optional[int]:
    """Menor n > c con Pa(LTPD) <= β. Pa decrece con n, así que se usa bisección."""
    lo = c + 1
    if lo > max_n or _scalar_pa(max_n, c, ltpd, distribution, lot_size) > beta:
        return None
    hi = max_n
    while lo < hi:
        mid = (lo + hi) // 2
        if _scalar_pa(mid, c, ltpd, distribution, lot_size) <= beta:
            hi = mid
        else:
            lo = mid + 1
    return lo


def find_single_plan(
    aql: float,
    ltpd: float,
    alpha: float = 0.05,
    beta: float = 0.10,
    distribution: str = "binomial",
    lot_size: Optional[int] = None,
    max_n: Optional[int] = None,
) -> DesignSearch:
    """Busca el plan (n, c) con el menor n que cumple ambos riesgos.

    Para cada c = 0, 1, 2, ... el menor n que cumple Pa(LTPD) <= β es n_β(c),
    creciente en c. Si ese n también cumple Pa(AQL) >= 1 - α, ningún plan con
    otro c puede tener un n menor: con c menores no hay n que cumpla los dos
    riesgos (los n mayores que n_β bajan aún más Pa(AQL)) y con c mayores
    n_β es mayor. Es una búsqueda exacta, no la lectura de un nomograma.
    """
    if not 0 < aql < ltpd < 1:
        raise ValueError("Se requiere 0 < AQL < LTPD < 1")
    if not (0 < alpha < 1 and 0 < beta < 1):
        raise ValueError("α y β deben estar entre 0 y 1")
    _validate_distribution(distribution, lot_size, 1)
    if max_n is None:
        max_n = lot_size if lot_size is not None else 100_000
    if lot_size is not None:
        max_n = min(max_n, lot_size)

    previous: Optional[tuple[int, int, float, float]] = None
    c = 0
    while c < max_n:
        n_beta = _min_n_for_beta(c, ltpd, beta, distribution, lot_size, max_n)
        if n_beta is None:
            break
        pa_aql = _scalar_pa(n_beta, c, aql, distribution, lot_size)
        pa_ltpd = _scalar_pa(n_beta, c, ltpd, distribution, lot_size)
        if pa_aql >= 1 - alpha:
            search = DesignSearch(aql=aql, alpha=alpha, ltpd=ltpd, beta=beta, n=n_beta, c=c)
            if previous is not None:
                pc, pn, pal, pbe = previous
                search.previous_c = pc
                search.previous_n = pn
                search.previous_alpha = pal
                search.previous_beta = pbe
                search.previous_feasible_beta = True
            return search
        previous = (c, n_beta, 1 - pa_aql, pa_ltpd)
        c += 1
    limit = f"N = {lot_size}" if lot_size is not None else f"n = {max_n}"
    raise ValueError(
        f"No existe un plan simple con n <= {limit} que cumpla α = {fmt(alpha)} en AQL = {fmt(aql)} "
        f"y β = {fmt(beta)} en LTPD = {fmt(ltpd)}. Acerque los riesgos o separe más AQL y LTPD."
    )


# --------------------------------------------------------------------------
# Curvas del plan simple
# --------------------------------------------------------------------------


def _p_max(pa, levels: list[float]) -> float:
    """Fracción defectuosa hasta la que se grafica: donde Pa cae a 0.005,
    o 1.5 veces el mayor valor de referencia (AQL, LTPD), lo que sea mayor."""
    target = 0.005
    if pa(1.0) > target:
        p_end = 1.0
    else:
        p_end = float(optimize.brentq(lambda q: pa(q) - target, 1e-12, 1.0, xtol=1e-10))
    for v in levels:
        if v is not None:
            p_end = max(p_end, 1.5 * v)
    return min(1.0, p_end)


def _p_grid(p_end: float, lot_size: Optional[int], distribution: str, points: int = 101) -> np.ndarray:
    if distribution == "hypergeometric":
        d_end = int(math.ceil(p_end * lot_size))
        d = np.unique(np.rint(np.linspace(0, d_end, points)).astype(int))
        return d / lot_size
    return np.linspace(0.0, p_end, points)


def _curve(xs, ys) -> list[CurvePoint]:
    return [CurvePoint(x=float(x), y=float(y)) for x, y in zip(xs, ys)]


def _aoq_single(p, n: int, c: int, distribution: str, lot_size: Optional[int]):
    pa = prob_accept(n, c, p, distribution, lot_size)
    factor = (lot_size - n) / lot_size if lot_size is not None else 1.0
    return pa * np.asarray(p) * factor


def _aoql_single(n: int, c: int, distribution: str, lot_size: Optional[int], p_end: float) -> tuple[float, float]:
    """Máximo de la curva AOQ y la fracción donde ocurre.

    Binomial y Poisson: rejilla fina y refinamiento con `minimize_scalar`.
    Hipergeométrica: máximo exacto sobre todos los D = 0..N (p discreto).
    """
    if distribution == "hypergeometric":
        d = np.arange(0, lot_size + 1)
        p = d / lot_size
        aoq = _aoq_single(p, n, c, distribution, lot_size)
        i = int(np.argmax(aoq))
        return float(aoq[i]), float(p[i])
    grid = np.linspace(0.0, p_end, 2001)
    aoq = _aoq_single(grid, n, c, distribution, lot_size)
    i = int(np.argmax(aoq))
    lo, hi = grid[max(i - 1, 0)], grid[min(i + 1, grid.size - 1)]
    res = optimize.minimize_scalar(
        lambda q: -float(_aoq_single(q, n, c, distribution, lot_size)),
        bounds=(lo, hi),
        method="bounded",
        options={"xatol": 1e-10},
    )
    best_p, best = float(res.x), float(-res.fun)
    if best < aoq[i]:
        best_p, best = float(grid[i]), float(aoq[i])
    return best, best_p


def evaluate_single_plan(
    n: int,
    c: int,
    lot_size: Optional[int] = None,
    distribution: str = "binomial",
    aql: Optional[float] = None,
    ltpd: Optional[float] = None,
    alpha: Optional[float] = None,
    beta: Optional[float] = None,
    search: Optional[DesignSearch] = None,
    reference_plan: Optional[tuple[int, int]] = None,
) -> SinglePlanResult:
    """Evalúa un plan simple (n, c): α y β reales, curvas OC, AOQ y ATI, AOQL.

    `alpha` y `beta` son los riesgos objetivo (si se conocen) y solo se usan
    en la interpretación. `reference_plan` permite comparar con otro plan,
    por ejemplo el leído en un nomograma.
    """
    n, c = int(n), int(c)
    if n < 1 or c < 0:
        raise ValueError("Se requiere n >= 1 y c >= 0")
    if c >= n:
        raise ValueError(f"Con c = {c} >= n = {n} el plan acepta todos los lotes")
    _validate_distribution(distribution, lot_size, n)

    def pa(q):
        return _scalar_pa(n, c, q, distribution, lot_size)

    alpha_actual = 1 - pa(aql) if aql is not None else None
    beta_actual = pa(ltpd) if ltpd is not None else None
    p_end = _p_max(pa, [aql, ltpd])
    p = _p_grid(p_end, lot_size, distribution)
    pa_curve = prob_accept(n, c, p, distribution, lot_size)
    aoq = _aoq_single(p, n, c, distribution, lot_size)
    aoql, aoql_at = _aoql_single(n, c, distribution, lot_size, p_end)
    ati = None
    if lot_size is not None:
        ati = _curve(p, n + (1 - pa_curve) * (lot_size - n))

    result = SinglePlanResult(
        n=n,
        c=c,
        distribution=distribution,
        alpha_actual=None if alpha_actual is None else float(alpha_actual),
        beta_actual=None if beta_actual is None else float(beta_actual),
        oc_curve=_curve(p, pa_curve),
        aoq_curve=_curve(p, aoq),
        aoql=aoql,
        aoql_at=aoql_at,
        ati_curve=ati,
    )
    reference = None
    if reference_plan is not None:
        rn, rc = reference_plan
        _validate_distribution(distribution, lot_size, rn)
        reference = {
            "n": int(rn),
            "c": int(rc),
            "alpha_actual": None if aql is None else 1 - _scalar_pa(rn, rc, aql, distribution, lot_size),
            "beta_actual": None if ltpd is None else _scalar_pa(rn, rc, ltpd, distribution, lot_size),
        }
    result.interpretation = interpret_single_plan(
        result,
        aql=aql,
        ltpd=ltpd,
        alpha=alpha,
        beta=beta,
        lot_size=lot_size,
        search=search,
        reference=reference,
        pa_at=pa,
    )
    return result


def design_single_plan(
    aql: float,
    ltpd: float,
    alpha: float = 0.05,
    beta: float = 0.10,
    lot_size: Optional[int] = None,
    distribution: str = "binomial",
    reference_plan: Optional[tuple[int, int]] = None,
) -> SinglePlanResult:
    """Diseña el plan simple de menor n que cumple α en AQL y β en LTPD,
    y lo evalúa (curvas OC, AOQ, ATI y AOQL)."""
    search = find_single_plan(aql, ltpd, alpha, beta, distribution, lot_size)
    return evaluate_single_plan(
        search.n,
        search.c,
        lot_size=lot_size,
        distribution=distribution,
        aql=aql,
        ltpd=ltpd,
        alpha=alpha,
        beta=beta,
        search=search,
        reference_plan=reference_plan,
    )


# --------------------------------------------------------------------------
# Plan doble
# --------------------------------------------------------------------------


def double_plan_probabilities(n1: int, c1: int, r1: int, n2: int, c2: int, p):
    """Devuelve (Pa^I, Pa^II, P(segunda muestra)) para un plan doble con
    muestreo binomial (Montgomery, cap. 15, plan doble)."""
    p = np.atleast_1d(np.asarray(p, dtype=float))
    pa1 = stats.binom.cdf(c1, n1, p)
    pa2 = np.zeros_like(p)
    for d in range(c1 + 1, r1):
        if c2 - d < 0:
            continue
        pa2 = pa2 + stats.binom.pmf(d, n1, p) * stats.binom.cdf(c2 - d, n2, p)
    p_second = stats.binom.cdf(r1 - 1, n1, p) - pa1
    return pa1, pa2, p_second


def evaluate_double_plan(
    n1: int,
    c1: int,
    r1: int,
    n2: int,
    c2: int,
    lot_size: Optional[int] = None,
    aql: Optional[float] = None,
    ltpd: Optional[float] = None,
) -> DoublePlanResult:
    """Curvas OC, ASN, aceptación en la primera muestra, AOQ y ATI de un plan doble.

    Reglas: se acepta si d1 <= c1; se rechaza si d1 >= r1; en otro caso se
    toma la segunda muestra y se acepta si d1 + d2 <= c2.
    """
    if not (n1 >= 1 and n2 >= 1 and c1 >= 0 and c2 >= c1):
        raise ValueError("Se requiere n1, n2 >= 1 y c2 >= c1 >= 0")
    if r1 < c1 + 1:
        raise ValueError("El número de rechazo r1 debe ser mayor que c1")
    if lot_size is not None and n1 + n2 > lot_size:
        raise ValueError(f"n1 + n2 = {n1 + n2} supera el tamaño de lote N = {lot_size}")

    def pa_total(q: float) -> float:
        a, b, _ = double_plan_probabilities(n1, c1, r1, n2, c2, q)
        return float(a[0] + b[0])

    p_end = _p_max(pa_total, [aql, ltpd])
    p = np.linspace(0.0, p_end, 101)
    pa1, pa2, p_second = double_plan_probabilities(n1, c1, r1, n2, c2, p)
    pa = pa1 + pa2

    def aoq_of(q):
        a, b, _ = double_plan_probabilities(n1, c1, r1, n2, c2, q)
        q = np.atleast_1d(q)
        if lot_size is None:
            return q * (a + b)
        return q * (a * (lot_size - n1) + b * (lot_size - n1 - n2)) / lot_size

    aoq = aoq_of(p)
    fine = np.linspace(0.0, p_end, 2001)
    aoq_fine = aoq_of(fine)
    i = int(np.argmax(aoq_fine))
    res = optimize.minimize_scalar(
        lambda q: -float(aoq_of(q)[0]),
        bounds=(fine[max(i - 1, 0)], fine[min(i + 1, fine.size - 1)]),
        method="bounded",
        options={"xatol": 1e-10},
    )
    aoql_at, aoql = float(res.x), float(-res.fun)
    if aoql < aoq_fine[i]:
        aoql_at, aoql = float(fine[i]), float(aoq_fine[i])

    ati = None
    if lot_size is not None:
        ati = _curve(p, n1 * pa1 + (n1 + n2) * pa2 + lot_size * (1 - pa))

    result = DoublePlanResult(
        oc_curve=_curve(p, pa),
        asn_curve=_curve(p, n1 + n2 * p_second),
        first_sample_accept_curve=_curve(p, pa1),
        alpha_actual=None if aql is None else 1 - pa_total(aql),
        beta_actual=None if ltpd is None else pa_total(ltpd),
        aoq_curve=_curve(p, aoq),
        aoql=aoql,
        ati_curve=ati,
        aoql_at=aoql_at,
    )
    result.interpretation = interpret_double_plan(
        result,
        n1=n1,
        c1=c1,
        r1=r1,
        n2=n2,
        c2=c2,
        lot_size=lot_size,
        aql=aql,
        ltpd=ltpd,
        aoql_at=aoql_at,
        probabilities=lambda q: tuple(float(v[0]) for v in double_plan_probabilities(n1, c1, r1, n2, c2, q)),
    )
    return result
