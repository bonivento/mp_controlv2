"""Diseño de gráficos de control: ARL0, ARL1, ATS, curvas OC y comparación de diseños.

Fuente: Montgomery, *Introduction to Statistical Quality Control*:

- Cap. 6, sección "The Operating-Characteristic Function" del gráfico X-barra:
  con límites μ0 ± L·σ/√n y un desplazamiento μ1 = μ0 + δ·σ,
      β(δ) = Φ(L - δ√n) - Φ(-L - δ√n).
  Individuales es el mismo caso con n = 1.
- Cap. 5 y 6, longitud promedio de corrida: con muestras independientes la
  longitud de corrida es geométrica, ARL = 1/P(señal):
      ARL0 = 1/α, con α = 2Φ(-L)  (370.4 para L = 3),
      ARL1 = 1/(1 - β).
  Tiempo promedio hasta la señal: ATS = ARL·h, con h el intervalo entre muestras.
- Cap. 7, curvas OC de los gráficos p y c: con D ~ Binomial(n, p),
      β = P(n·LCI <= D <= n·LCS | p);
  con x ~ Poisson(c), β = P(LCI <= x <= LCS | c). Como D y x son enteros, la
  probabilidad de falsa alarma no es 0.0027 y el ARL0 real difiere de 370.4.

Cuando se activan reglas suplementarias (Western Electric o Nelson) la
longitud de corrida deja de ser geométrica y se estima por Monte Carlo:
corridas simuladas hasta la primera señal, evaluadas con
`app.spc.rules.signal_matrix` (la misma lógica de los gráficos). La
simulación está acotada por número de corridas, longitud máxima y un
presupuesto total de observaciones, para terminar en pocos segundos.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

import numpy as np
from scipy import stats

from . import rules as rules_mod
from .descriptive import CurvePoint
from .interpretation import Interpretation, interpret_arl, interpret_compare

# Reglas equivalentes a "un punto fuera de los límites": no requieren simulación.
SHEWHART_RULES = frozenset({"WE1", "N1"})

# Puntos de historia que se arrastran entre bloques de simulación: la regla
# con ventana más larga (Nelson 7) mira 15 puntos.
_HISTORY = 15

# Presupuesto de observaciones simuladas por llamada (todas las condiciones).
# Con las doce reglas se evalúan unos 7 millones de puntos por segundo.
DEFAULT_MAX_POINTS = 12_000_000

Detector = Callable[[np.ndarray], np.ndarray]


@dataclass
class ArlRow:
    shift: float
    beta: Optional[float]
    arl1: float
    ats1: float
    units_to_detect: float
    std_error: Optional[float] = None


@dataclass
class ArlResult:
    """Equivale a `ArlResponse`."""

    method: str
    alpha: Optional[float]
    arl0: float
    ats0: float
    sampling_load: float
    rows: list[ArlRow]
    oc_curve: list[CurvePoint]
    arl_curve: list[CurvePoint]
    interpretation: Interpretation = field(default_factory=lambda: Interpretation(summary=""))
    # Error estándar del ARL0; solo en simulación.
    arl0_std_error: Optional[float] = None


@dataclass
class CompareRow:
    n: int
    limit_width: float
    sampling_interval: float
    arl0: float
    ats0: float
    arl1: float
    ats1: float
    sampling_load: float


@dataclass
class CompareResult:
    """Equivale a `CompareResponse`."""

    shift: float
    rows: list[CompareRow]
    interpretation: Interpretation = field(default_factory=lambda: Interpretation(summary=""))


@dataclass
class SimulationEstimate:
    """ARL estimado por Monte Carlo."""

    arl: float
    std_error: float
    runs: int
    censored: int
    points: int


@dataclass
class ChartModel:
    """Límites del gráfico y probabilidad de señal por muestra (regla WE1)."""

    chart: str
    n: int
    limit_width: float
    center: float
    ucl: float
    lcl: float
    sigma: float  # desviación estándar del estadístico graficado
    lcl_truncated: bool = False
    ucl_truncated: bool = False

    @property
    def symmetric(self) -> bool:
        return not (self.lcl_truncated or self.ucl_truncated)


# --------------------------------------------------------------------------
# Fórmulas exactas
# --------------------------------------------------------------------------


def xbar_signal_probability(shift, n: int = 1, limit_width: float = 3.0):
    """1 - β(δ) = P(señal) para X-barra con límites de L sigma (Montgomery, cap. 6).

    Se calcula como Φ(-L - δ√n) + [1 - Φ(L - δ√n)] con la función de
    supervivencia, para no perder precisión cuando β está cerca de 1.
    """
    k = np.asarray(shift, dtype=float) * math.sqrt(n)
    return stats.norm.sf(limit_width - k) + stats.norm.cdf(-limit_width - k)


def xbar_beta(shift, n: int = 1, limit_width: float = 3.0):
    """β(δ) = Φ(L - δ√n) - Φ(-L - δ√n) (Montgomery, cap. 6, función OC de X-barra)."""
    k = np.asarray(shift, dtype=float) * math.sqrt(n)
    return stats.norm.cdf(limit_width - k) - stats.norm.cdf(-limit_width - k)


def p_chart_model(p0: float, n: int, limit_width: float = 3.0) -> ChartModel:
    """Límites del gráfico p con p conocido: p0 ± L·√(p0(1-p0)/n), truncados en [0, 1]
    (Montgomery, cap. 7)."""
    if not 0 < p0 < 1:
        raise ValueError("p0 debe estar entre 0 y 1")
    s = math.sqrt(p0 * (1 - p0) / n)
    ucl, lcl = p0 + limit_width * s, p0 - limit_width * s
    return ChartModel("p", n, limit_width, p0, min(ucl, 1.0), max(lcl, 0.0), s,
                      lcl_truncated=lcl <= 0, ucl_truncated=ucl >= 1)


def c_chart_model(c0: float, limit_width: float = 3.0) -> ChartModel:
    """Límites del gráfico c con c conocido: c0 ± L·√c0, LCI truncado en 0 (Montgomery, cap. 7)."""
    if not c0 > 0:
        raise ValueError("c0 debe ser positivo")
    s = math.sqrt(c0)
    ucl, lcl = c0 + limit_width * s, c0 - limit_width * s
    return ChartModel("c", 1, limit_width, c0, ucl, max(lcl, 0.0), s, lcl_truncated=lcl <= 0)


_EPS = 1e-9


def _count_bounds(model: ChartModel) -> tuple[int, int]:
    """Conteos enteros [a, b] que NO dan señal (dentro de los límites, inclusive).

    Para p el conteo es D = n·p̂; para c es x. Un punto exactamente sobre el
    límite no es señal (la regla es "más allá del límite").
    """
    scale = model.n if model.chart == "p" else 1
    a = int(math.ceil(model.lcl * scale - _EPS))
    b = int(math.floor(model.ucl * scale + _EPS))
    return max(a, 0), b


def count_chart_beta(model: ChartModel, level) -> np.ndarray:
    """β = P(a <= conteo <= b) con conteo binomial (p) o Poisson (c) (Montgomery, cap. 7)."""
    a, b = _count_bounds(model)
    level = np.asarray(level, dtype=float)
    if model.chart == "p":
        upper = stats.binom.cdf(b, model.n, level)
        lower = stats.binom.cdf(a - 1, model.n, level) if a > 0 else 0.0
    else:
        upper = stats.poisson.cdf(b, level)
        lower = stats.poisson.cdf(a - 1, level) if a > 0 else 0.0
    return np.clip(upper - lower, 0.0, 1.0)


def count_chart_signal_probability(model: ChartModel, level) -> np.ndarray:
    """1 - β calculado por colas (sin cancelación): P(conteo > b) + P(conteo < a)."""
    a, b = _count_bounds(model)
    level = np.asarray(level, dtype=float)
    if model.chart == "p":
        up = stats.binom.sf(b, model.n, level)
        lo = stats.binom.cdf(a - 1, model.n, level) if a > 0 else 0.0
    else:
        up = stats.poisson.sf(b, level)
        lo = stats.poisson.cdf(a - 1, level) if a > 0 else 0.0
    return up + lo


def arl_from_signal_probability(p_signal: float) -> float:
    """ARL = 1/P(señal) (longitud de corrida geométrica)."""
    if not p_signal > 0:
        raise ValueError(
            "La probabilidad de señal es 0: el gráfico nunca daría una señal con este diseño "
            "(límites demasiado anchos o muestra demasiado pequeña)."
        )
    return 1.0 / float(p_signal)


# --------------------------------------------------------------------------
# Simulación Monte Carlo
# --------------------------------------------------------------------------


def simulate_run_lengths(
    sampler: Callable[[np.random.Generator, tuple[int, int]], np.ndarray],
    detector: Detector,
    runs: int,
    max_length: int,
    rng: np.random.Generator,
    max_points: int,
    history: int = _HISTORY,
    wave_size: int = 1000,
) -> tuple[np.ndarray, int, int]:
    """Longitudes de corrida simuladas hasta la primera señal.

    - `sampler(rng, (filas, columnas))` genera el estadístico graficado.
    - `detector(x)` recibe una matriz (filas × tiempo) y devuelve una matriz
      booleana del mismo tamaño con True donde se completa una señal.

    Las corridas se simulan en tandas de `wave_size`. Dentro de cada tanda se
    avanza por bloques de largo creciente; de cada corrida activa se arrastran
    los últimos `history` puntos para que las reglas con ventana vean la serie
    continua (las señales en esos puntos ya se evaluaron y se ignoran).

    Presupuesto: no se empieza una tanda nueva si ya se generaron
    `max_points` observaciones, de modo que, si falta cómputo, se usan menos
    corridas completas (más error estándar, sin sesgo) en lugar de cortar
    corridas. Una tanda ya empezada puede seguir hasta el doble del
    presupuesto para terminar sus corridas. Solo se censura una corrida si
    llega a `max_length`, si el presupuesto se agota dentro de la primera
    tanda o si una tanda posterior llega al doble del presupuesto; su longitud
    queda en el valor alcanzado, que es una cota inferior (se advierte en la
    interpretación).

    Devuelve (longitudes de las corridas simuladas, corridas censuradas,
    observaciones generadas).
    """
    lengths: list[np.ndarray] = []
    censored = 0
    points = 0
    done = 0
    while done < runs:
        if done > 0 and points >= max_points:
            break
        m = min(wave_size, runs - done)
        rl = np.zeros(m, dtype=float)
        active = np.arange(m)
        hist: Optional[np.ndarray] = None
        t0 = 0
        block = 64
        while active.size and t0 < max_length:
            remaining = (max_points - points) if done == 0 else (2 * max_points - points)
            if remaining <= 0:
                break
            b = min(block, max_length - t0, max(1, remaining // active.size))
            new = sampler(rng, (active.size, b))
            points += new.size
            x = new if hist is None else np.concatenate([hist, new], axis=1)
            off = 0 if hist is None else hist.shape[1]
            sig = detector(x)[:, off:]
            has = sig.any(axis=1)
            first = np.argmax(sig, axis=1)
            rl[active[has]] = t0 + first[has] + 1
            keep = ~has
            hist = x[keep, -history:] if x.shape[1] > history else x[keep]
            active = active[keep]
            t0 += b
            block = min(block * 2, 4096)
        if active.size:
            censored += int(active.size)
            rl[active] = t0
        lengths.append(rl)
        done += m
    return np.concatenate(lengths), censored, points


def _estimate(rl: np.ndarray, censored: int, points: int) -> SimulationEstimate:
    r = rl.size
    se = float(np.std(rl, ddof=1) / math.sqrt(r)) if r > 1 else 0.0
    return SimulationEstimate(arl=float(rl.mean()), std_error=se, runs=r, censored=censored, points=points)


def _default_detector(model: ChartModel, rules: Sequence[str]) -> Detector:
    """Detector basado en `app.spc.rules.signal_matrix` con los límites del modelo."""
    def detect(x: np.ndarray) -> np.ndarray:
        return rules_mod.signal_matrix(
            x,
            model.center,
            ucl=model.ucl,
            lcl=model.lcl,
            sigma=model.sigma,
            rules=list(rules),
            limit_width=model.limit_width,
            symmetric=model.symmetric,
        )

    return detect


def applicable_simulation_rules(model: ChartModel, rules: Sequence[str]) -> tuple[list[str], dict[str, str]]:
    """Reglas que el gráfico realmente aplicaría (las de zonas requieren límites simétricos)."""
    reason = (
        "los límites del gráfico no son simétricos (límite truncado), así que las zonas A, B "
        "y C no están definidas"
    )
    return rules_mod.applicable_rules(rules, model.symmetric, reason)


def _sampler_for(model: ChartModel, level: float):
    """Generador del estadístico graficado en un estado del proceso."""
    if model.chart in ("xbar", "individuals"):
        mean = level * math.sqrt(model.n)  # en unidades de σ/√n, con LC = 0

        def gen(rng, shape):
            return rng.standard_normal(shape) + mean

    elif model.chart == "p":

        def gen(rng, shape):
            return rng.binomial(model.n, level, size=shape) / model.n

    else:

        def gen(rng, shape):
            return rng.poisson(level, size=shape).astype(float)

    return gen


# --------------------------------------------------------------------------
# ARL de un diseño
# --------------------------------------------------------------------------


def _model_for(chart: str, n: int, limit_width: float, p0, c0) -> ChartModel:
    if chart in ("xbar", "individuals"):
        n_eff = 1 if chart == "individuals" else int(n)
        return ChartModel(chart, n_eff, limit_width, 0.0, limit_width, -limit_width, 1.0)
    if chart == "p":
        if p0 is None:
            raise ValueError("El gráfico p requiere p0 (fracción no conforme en control)")
        return p_chart_model(p0, int(n), limit_width)
    if chart == "c":
        if c0 is None:
            raise ValueError("El gráfico c requiere c0 (media de no conformidades en control)")
        return c_chart_model(c0, limit_width)
    raise ValueError(f"Gráfico no soportado: {chart!r}")


def _levels(chart: str, model: ChartModel, shifts, p0, p1, c0, c1) -> list[float]:
    """Estados fuera de control: δ para X-barra e individuales, p1 o c1 para atributos.
    Si no se envían p1 o c1 se usan 1.5, 2, 2.5 y 3 veces el valor en control."""
    if chart in ("xbar", "individuals"):
        return [float(s) for s in shifts]
    if chart == "p":
        vals = list(p1) if p1 else [p0 * k for k in (1.5, 2.0, 2.5, 3.0) if p0 * k < 1]
        for v in vals:
            if not 0 < v < 1:
                raise ValueError("Cada p1 debe estar entre 0 y 1")
        return [float(v) for v in vals]
    vals = list(c1) if c1 else [c0 * k for k in (1.5, 2.0, 2.5, 3.0)]
    for v in vals:
        if not v > 0:
            raise ValueError("Cada c1 debe ser positivo")
    return [float(v) for v in vals]


def _curve_grid(chart: str, model: ChartModel, levels: list[float], points: int = 61) -> np.ndarray:
    if chart in ("xbar", "individuals"):
        top = max([3.0] + [abs(v) for v in levels])
        return np.linspace(0.0, top, points)
    if chart == "p":
        top = min(0.999, max(levels + [model.ucl * 1.5, model.center * 3]))
        return np.linspace(0.0, top, points)[1:]
    top = max(levels + [model.ucl * 1.3])
    return np.linspace(0.0, top, points)[1:]


def _exact_signal(chart: str, model: ChartModel, level):
    if chart in ("xbar", "individuals"):
        return xbar_signal_probability(level, model.n, model.limit_width)
    return count_chart_signal_probability(model, level)


def _exact_beta(chart: str, model: ChartModel, level):
    if chart in ("xbar", "individuals"):
        return xbar_beta(level, model.n, model.limit_width)
    return count_chart_beta(model, level)


def compute_arl(
    chart: str,
    n: int = 1,
    limit_width: float = 3.0,
    sampling_interval: float = 1.0,
    shifts: Sequence[float] = (0.5, 1.0, 1.5, 2.0, 3.0),
    p0: Optional[float] = None,
    p1: Optional[Sequence[float]] = None,
    c0: Optional[float] = None,
    c1: Optional[Sequence[float]] = None,
    rules: Sequence[str] = ("WE1",),
    max_runs: int = 5000,
    max_length: int = 20000,
    seed: Optional[int] = 12345,
    detector: Optional[Callable[[ChartModel, Sequence[str]], Detector]] = None,
    force_simulation: bool = False,
    max_points: int = DEFAULT_MAX_POINTS,
) -> ArlResult:
    """ARL0, ARL1, ATS, carga muestral y curvas OC y ARL de un gráfico.

    - `chart`: "xbar", "individuals", "p" o "c".
    - Método exacto si las reglas son solo WE1/N1 (un punto fuera de límites).
      Con reglas suplementarias, Monte Carlo con `max_runs` corridas por
      estado, cada una hasta `max_length` muestras, y a lo sumo `max_points`
      observaciones simuladas en total.
    - `detector(model, rules)` permite inyectar otro evaluador de reglas; por
      defecto se usa `app.spc.rules.signal_matrix`.
    - `force_simulation` obliga a simular aunque solo esté WE1 (sirve para
      validar la simulación contra la fórmula exacta).
    - Unidades hasta detectar = ARL1·n (n = 1 en individuales y c).
    """
    if sampling_interval <= 0:
        raise ValueError("El intervalo entre muestras h debe ser positivo")
    if limit_width <= 0:
        raise ValueError("L debe ser positivo")
    if n < 1:
        raise ValueError("n debe ser al menos 1")
    model = _model_for(chart, n, limit_width, p0, c0)
    levels = _levels(chart, model, shifts, p0, p1, c0, c1)
    units_per_sample = model.n if chart in ("xbar", "p") else 1
    h = float(sampling_interval)
    load = units_per_sample / h
    in_control = 0.0 if chart in ("xbar", "individuals") else model.center
    grid = _curve_grid(chart, model, levels)
    oc_curve = [CurvePoint(x=float(x), y=float(y)) for x, y in zip(grid, _exact_beta(chart, model, grid))]

    requested = list(dict.fromkeys(rules)) or ["WE1"]
    simulate = force_simulation or not set(requested) <= SHEWHART_RULES
    skipped: dict[str, str] = {}
    sim_info: dict = {}

    if not simulate:
        alpha = float(_exact_signal(chart, model, in_control))
        arl0 = arl_from_signal_probability(alpha)
        rows = []
        for lv in levels:
            ps = float(_exact_signal(chart, model, lv))
            arl1 = arl_from_signal_probability(ps)
            rows.append(
                ArlRow(
                    shift=lv,
                    beta=float(_exact_beta(chart, model, lv)),
                    arl1=arl1,
                    ats1=arl1 * h,
                    units_to_detect=arl1 * units_per_sample,
                )
            )
        sig_curve = np.asarray(_exact_signal(chart, model, grid), dtype=float)
        arl_curve = [
            CurvePoint(x=float(x), y=float(1.0 / s))
            for x, s in zip(grid, sig_curve)
            if s > 0
        ]
        method = "exact"
    else:
        applied, skipped = applicable_simulation_rules(model, requested)
        if not applied:
            raise ValueError(
                "Ninguna de las reglas pedidas se puede aplicar a este gráfico: " + " ".join(skipped.values())
            )
        make = detector or _default_detector
        detect = make(model, applied)
        states = [in_control] + levels
        # Los estados fuera de control (corridas cortas) se simulan primero y
        # el presupuesto que no usan pasa al estado en control, el más caro.
        order = list(range(1, len(states))) + [0]
        estimates: list[Optional[SimulationEstimate]] = [None] * len(states)
        used = 0
        for k, i in enumerate(order):
            budget = max((int(max_points) - used) // (len(order) - k), int(max_runs))
            rng = np.random.default_rng(None if seed is None else [int(seed), i])
            rl, cens, pts = simulate_run_lengths(
                _sampler_for(model, states[i]), detect, int(max_runs), int(max_length), rng, budget
            )
            used += pts
            estimates[i] = _estimate(rl, cens, pts)
        est0 = estimates[0]
        alpha = None
        arl0 = est0.arl
        rows = [
            ArlRow(
                shift=lv,
                beta=None,
                arl1=e.arl,
                ats1=e.arl * h,
                units_to_detect=e.arl * units_per_sample,
                std_error=e.std_error,
            )
            for lv, e in zip(levels, estimates[1:])
        ]
        pts_sorted = sorted([(in_control, arl0)] + [(r.shift, r.arl1) for r in rows])
        arl_curve = [CurvePoint(x=float(x), y=float(y)) for x, y in pts_sorted]
        method = "simulation"
        sim_info = {
            "applied": applied,
            "arl0_std_error": est0.std_error,
            "runs": int(max_runs),
            "runs_used": [e.runs for e in estimates],
            "max_length": int(max_length),
            "censored": [e.censored for e in estimates],
            "points": sum(e.points for e in estimates),
            "seed": seed,
            "states": states,
        }
        # Referencia exacta de la regla de un punto fuera de límites, para
        # mostrar cuánto cambian ARL0 y ARL1 al agregar reglas suplementarias.
        try:
            sim_info["shewhart_arl0"] = arl_from_signal_probability(
                float(_exact_signal(chart, model, in_control))
            )
            sim_info["shewhart_arl1"] = [
                arl_from_signal_probability(float(_exact_signal(chart, model, lv))) for lv in levels
            ]
        except ValueError:
            sim_info["shewhart_arl0"] = None
            sim_info["shewhart_arl1"] = [None] * len(levels)

    result = ArlResult(
        method=method,
        alpha=alpha,
        arl0=float(arl0),
        ats0=float(arl0 * h),
        sampling_load=float(load),
        rows=rows,
        oc_curve=oc_curve,
        arl_curve=arl_curve,
    )
    if method == "simulation":
        result.arl0_std_error = float(sim_info["arl0_std_error"])
    result.interpretation = interpret_arl(
        result,
        chart=chart,
        n=units_per_sample,
        limit_width=limit_width,
        sampling_interval=h,
        model=model,
        count_bounds=_count_bounds(model) if chart in ("p", "c") else None,
        rules_requested=requested,
        rules_skipped=skipped,
        simulation=sim_info or None,
        attribute_defaults=(chart == "p" and not p1) or (chart == "c" and not c1),
    )
    return result


# --------------------------------------------------------------------------
# Comparación de diseños X-barra
# --------------------------------------------------------------------------


def compare_designs(
    n_values: Sequence[int],
    limit_widths: Sequence[float] = (3.0,),
    sampling_intervals: Sequence[float] = (1.0,),
    shift: float = 1.0,
) -> CompareResult:
    """Tabla de diseños X-barra (n, L, h) con ARL0, ATS0, ARL1, ATS1 y carga n/h
    para un desplazamiento δ, con las fórmulas exactas de Montgomery, cap. 6."""
    if not n_values:
        raise ValueError("Se requiere al menos un tamaño de muestra")
    rows = []
    for n in n_values:
        if int(n) < 1:
            raise ValueError("Cada n debe ser al menos 1")
        for L in limit_widths:
            if L <= 0:
                raise ValueError("Cada L debe ser positivo")
            a = float(xbar_signal_probability(0.0, int(n), L))
            arl0 = arl_from_signal_probability(a)
            arl1 = arl_from_signal_probability(float(xbar_signal_probability(shift, int(n), L)))
            for h in sampling_intervals:
                if h <= 0:
                    raise ValueError("Cada h debe ser positivo")
                rows.append(
                    CompareRow(
                        n=int(n),
                        limit_width=float(L),
                        sampling_interval=float(h),
                        arl0=arl0,
                        ats0=arl0 * h,
                        arl1=arl1,
                        ats1=arl1 * h,
                        sampling_load=int(n) / h,
                    )
                )
    result = CompareResult(shift=float(shift), rows=rows)
    result.interpretation = interpret_compare(result)
    return result
