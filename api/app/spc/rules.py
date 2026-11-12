"""Reglas de corrida: Western Electric (WE1..WE4) y Nelson (N1..N8).

Fuentes:
- Montgomery, *Introduction to Statistical Quality Control*, sección 5.3.6
  ("Discussion of Sensitizing Rules for Control Charts"), tabla 5.1 (reglas
  Western Electric y reglas suplementarias).
- Western Electric Company (1956), *Statistical Quality Control Handbook*.
- Nelson, L. S. (1984), "The Shewhart Control Chart — Tests for Special Causes",
  *Journal of Quality Technology* 16(4), 237-239.

Definiciones implementadas (sigma = desviación estándar del estadístico graficado,
z = (x - LC) / sigma):

| Id  | Regla                                                                  | Usa zonas |
|-----|------------------------------------------------------------------------|-----------|
| WE1 | 1 punto fuera de los límites de control                                | no        |
| WE2 | 2 de 3 consecutivos más allá de 2 sigma, del mismo lado                | sí        |
| WE3 | 4 de 5 consecutivos más allá de 1 sigma, del mismo lado                | sí        |
| WE4 | 8 consecutivos del mismo lado de la línea central                      | no        |
| N1  | 1 punto fuera de los límites de control                                | no        |
| N2  | 9 consecutivos del mismo lado de la línea central                      | no        |
| N3  | 6 consecutivos estrictamente crecientes o decrecientes                 | no        |
| N4  | 14 consecutivos que alternan subiendo y bajando                        | no        |
| N5  | 2 de 3 consecutivos más allá de 2 sigma, del mismo lado                | sí        |
| N6  | 4 de 5 consecutivos más allá de 1 sigma, del mismo lado                | sí        |
| N7  | 15 consecutivos dentro de 1 sigma (zona C), a ambos lados              | sí        |
| N8  | 8 consecutivos a más de 1 sigma (ninguno en zona C), a cualquier lado  | sí        |

Convenciones (documentadas para el validador):
- N4 es la prueba de Nelson de 14 puntos que alternan en DIRECCIÓN (sube, baja,
  sube...), es decir 13 diferencias consecutivas con signo alternado. No es
  "alternar a lados de la línea central". Una diferencia nula rompe la alternancia.
- N3 cuenta 6 puntos (5 diferencias del mismo signo); un empate rompe la tendencia.
- Las comparaciones son estrictas ("más allá de"): un punto exactamente sobre el
  límite, sobre 2 sigma o sobre la línea central no cuenta. Para evitar señales
  falsas por redondeo se usa una tolerancia relativa de 1e-9.
- Un punto sobre la línea central no está "de ningún lado": rompe la corrida.
- Reglas "k de m": la señal se marca en un punto que cumple la condición cuando,
  en la ventana de m puntos que termina en él, hay al menos k que la cumplen del
  mismo lado. Al inicio de la serie se usan los puntos disponibles (equivale a
  suponer que los anteriores estaban en la zona central, como en las cadenas de
  Markov de Champ y Woodall, 1987).
- Cada señal se reporta en el punto donde se completa. Si la condición sigue
  cumpliéndose (por ejemplo, un décimo punto del mismo lado), se marca de nuevo
  en cada punto adicional, como hace Minitab.
- Zonas A, B y C solo existen con límites simétricos (X-barra, individuales y
  atributos sin truncar). En R, S y en atributos con algún límite truncado solo
  se aplican WE1, WE4, N1, N2, N3 y N4; las demás se informan como omitidas con
  su motivo.
- En esos paneles asimétricos WE4 y N2 se aplican, pero la probabilidad de caer
  por encima de la línea central no es 1/2. En estadísticos continuos (R, S) su
  ARL0 real es menor que el nominal (cadenas de Markov del validador: WE4 da
  173,7 en R con n = 2 frente a 255). En conteos (p, np, c, u truncados) la
  tasa de falsas alarmas es distinta de la nominal en uno u otro sentido: mayor
  si la línea central no es un valor posible del conteo (42,8 en p con n = 100 y
  p̄ = 0,0102) y mucho menor si coincide con uno, porque los puntos exactamente
  sobre la línea cortan la racha (WE4 da 1 924 en c con c̄ = 2 y 1 071 con
  c̄ = 4, frente a 255; 4 508 en p con n·p̄ = 1), con pérdida de sensibilidad.
  `evaluate_rules` agrega entonces una advertencia (`RuleOutcome.warnings`, una
  sola por serie) que pide tomar la señal como indicio a confirmar. N3 y N4
  dependen solo del orden de los valores: con datos continuos e independientes
  su ARL0 no cambia por la asimetría y con conteos los empates lo alargan; la
  advertencia lo dice.
- Panel MR (`serially_correlated=True`): los rangos móviles consecutivos
  comparten una observación y están correlacionados, además de ser asimétricos;
  el validador midió ARL0 de 94 para WE4 (255 nominal), 154 para N2 (511) y 257
  para N3 (425). Por eso en MR solo se aplican WE1 y N1; las demás reglas se
  informan como omitidas con ese motivo.
- Con límites variables por punto (p y u con n variable) la zona de cada punto
  se calcula con el sigma de ese punto.
- Los puntos excluidos no participan: se quitan de la serie antes de evaluar
  (la corrida "salta" sobre ellos) y nunca reciben señal.
- N3 y N4 se evalúan sobre los valores graficados, no sobre z.

La función `evaluate_rules` sirve para un gráfico real (una serie, con etiquetas
y exclusiones). `signal_matrix` y `first_signal` son la versión vectorizada para
simulación de ARL: reciben una matriz (réplicas × tiempo).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Callable, Iterable, Optional, Sequence

import numpy as np

RULE_IDS: tuple[str, ...] = (
    "WE1", "WE2", "WE3", "WE4",
    "N1", "N2", "N3", "N4", "N5", "N6", "N7", "N8",
)
WESTERN_ELECTRIC: tuple[str, ...] = ("WE1", "WE2", "WE3", "WE4")
NELSON: tuple[str, ...] = ("N1", "N2", "N3", "N4", "N5", "N6", "N7", "N8")

_REL_TOL = 1e-9

# Reglas que solo miran el punto contra los límites.
LIMIT_RULES: tuple[str, ...] = ("WE1", "N1")
# Reglas sin zonas que se siguen aplicando en paneles asimétricos.
SIDE_RUN_RULES: tuple[str, ...] = ("WE4", "N2")      # rachas de un lado de la LC
ORDER_RULES: tuple[str, ...] = ("N3", "N4")          # tendencia y alternancia
ASYMMETRY_SENSITIVE_RULES: tuple[str, ...] = SIDE_RUN_RULES + ORDER_RULES

SERIAL_CORRELATION_REASON = (
    "en el gráfico de rangos móviles solo se evalúa el punto fuera de límites, porque dos rangos "
    "móviles consecutivos comparten una observación y están correlacionados (además de ser "
    "asimétricos); con esta regla la tasa de falsas alarmas sería varias veces la nominal"
)

# Códigos que devuelve cada regla por punto.
NO_SIGNAL = 0
UP = 1        # por encima / creciente
DOWN = -1     # por debajo / decreciente
BOTH = 2      # regla sin dirección (N4, N7, N8)


# --------------------------------------------------------------------------
# Estructuras
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Violation:
    """Señal en un punto. Se convierte 1 a 1 en `RuleViolation` del contrato."""

    rule: str
    index: int
    description: str


@dataclass
class RuleOutcome:
    """Resultado de evaluar reglas sobre una serie."""

    violations: list[Violation] = field(default_factory=list)
    applied: list[str] = field(default_factory=list)
    skipped: dict[str, str] = field(default_factory=dict)  # id -> motivo en español
    warnings: list[str] = field(default_factory=list)      # advertencias de la serie, en español

    @property
    def indices(self) -> list[int]:
        return sorted({v.index for v in self.violations})


@dataclass(frozen=True)
class ControlLimits:
    """Límites de un panel. Cada campo es escalar o un arreglo por punto.

    `sigma` es la desviación estándar del estadístico graficado (no del proceso);
    con ella se construyen las zonas. `symmetric` indica si las zonas A/B/C
    tienen sentido (límites simétricos y distribución aproximadamente simétrica).
    `serially_correlated` marca un estadístico con correlación serial por
    construcción (rangos móviles): solo admite WE1 y N1. `discrete` marca un
    conteo (p, np, c, u): cambia el texto de la advertencia de asimetría.
    """

    center: np.ndarray
    ucl: np.ndarray
    lcl: np.ndarray
    sigma: np.ndarray
    symmetric: bool
    limit_width: float = 3.0
    serially_correlated: bool = False
    discrete: bool = False

    def as_arrays(self, m: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Devuelve (center, ucl, lcl, sigma) como arreglos de largo m."""
        out = []
        for a in (self.center, self.ucl, self.lcl, self.sigma):
            a = np.asarray(a, dtype=float)
            out.append(np.broadcast_to(a, (m,)).astype(float) if a.ndim == 0 or a.shape == (1,)
                       else np.asarray(a, dtype=float))
        for a in out:
            if a.shape != (m,):
                raise ValueError("Los límites por punto deben tener el mismo largo que la serie.")
        return out[0], out[1], out[2], out[3]


@dataclass
class RuleInput:
    """Serie preparada para evaluar reglas. Todo en forma (réplicas, T)."""

    x: np.ndarray
    center: np.ndarray
    ucl: np.ndarray
    lcl: np.ndarray
    z: Optional[np.ndarray]  # None cuando las zonas no están definidas
    tol: np.ndarray

    @property
    def deviation(self) -> np.ndarray:
        return self.x - self.center


@dataclass(frozen=True)
class RuleSpec:
    id: str
    family: str
    needs_zones: bool
    func: Callable[[RuleInput], np.ndarray]
    template: dict[int, str]


# --------------------------------------------------------------------------
# Utilidades vectorizadas (eje -1 = tiempo)
# --------------------------------------------------------------------------


def _run_length(b: np.ndarray) -> np.ndarray:
    """Largo de la corrida de True que termina en cada t."""
    t = np.arange(b.shape[-1])
    last_false = np.maximum.accumulate(np.where(b, -1, t), axis=-1)
    return t - last_false


def _window_count(b: np.ndarray, m: int) -> np.ndarray:
    """Cantidad de True en la ventana de m puntos que termina en t (parcial al inicio)."""
    cs = np.cumsum(b.astype(np.int32), axis=-1)
    shifted = np.zeros_like(cs)
    if b.shape[-1] > m:
        shifted[..., m:] = cs[..., :-m]
    return cs - shifted


def _directional(up: np.ndarray, down: np.ndarray) -> np.ndarray:
    out = np.zeros(up.shape, dtype=np.int8)
    out[up] = UP
    out[down] = DOWN
    return out


def _diff_sign(inp: RuleInput) -> np.ndarray:
    """Signo de x_t - x_{t-1} (0 en t = 0 o si hay empate)."""
    s = np.zeros(inp.x.shape, dtype=np.int8)
    d = np.diff(inp.x, axis=-1)
    tol = np.maximum(inp.tol[..., 1:], inp.tol[..., :-1])
    s[..., 1:] = np.where(d > tol, 1, np.where(d < -tol, -1, 0))
    return s


# --------------------------------------------------------------------------
# Patrones reutilizables
# --------------------------------------------------------------------------


def beyond_limits(inp: RuleInput) -> np.ndarray:
    """Un punto por encima del LCS o por debajo del LCI."""
    return _directional(inp.x > inp.ucl + inp.tol, inp.x < inp.lcl - inp.tol)


def k_of_m_beyond(inp: RuleInput, k: int, m: int, zsig: float) -> np.ndarray:
    """k de m consecutivos más allá de zsig sigmas, del mismo lado."""
    z = inp.z
    up_q = z > zsig + _REL_TOL
    dn_q = z < -zsig - _REL_TOL
    up = up_q & (_window_count(up_q, m) >= k)
    dn = dn_q & (_window_count(dn_q, m) >= k)
    return _directional(up, dn)


def run_same_side(inp: RuleInput, length: int) -> np.ndarray:
    """`length` consecutivos estrictamente del mismo lado de la línea central."""
    d = inp.deviation
    up = _run_length(d > inp.tol) >= length
    dn = _run_length(d < -inp.tol) >= length
    return _directional(up, dn)


def run_trend(inp: RuleInput, length: int) -> np.ndarray:
    """`length` puntos consecutivos estrictamente crecientes o decrecientes."""
    s = _diff_sign(inp)
    up = _run_length(s == 1) >= length - 1
    dn = _run_length(s == -1) >= length - 1
    return _directional(up, dn)


def run_alternating(inp: RuleInput, length: int) -> np.ndarray:
    """`length` puntos consecutivos que alternan subiendo y bajando.

    `length` puntos tienen length-1 diferencias; deben alternar de signo, o sea
    length-2 cambios de signo consecutivos entre diferencias no nulas.
    """
    s = _diff_sign(inp)
    alt = np.zeros(s.shape, dtype=bool)
    alt[..., 2:] = (s[..., 2:] * s[..., 1:-1]) < 0
    hit = _run_length(alt) >= length - 2
    out = np.zeros(s.shape, dtype=np.int8)
    out[hit] = BOTH
    return out


def run_within(inp: RuleInput, length: int, zsig: float) -> np.ndarray:
    """`length` consecutivos con |z| < zsig (estratificación)."""
    hit = _run_length(np.abs(inp.z) < zsig - _REL_TOL) >= length
    out = np.zeros(hit.shape, dtype=np.int8)
    out[hit] = BOTH
    return out


def run_outside(inp: RuleInput, length: int, zsig: float) -> np.ndarray:
    """`length` consecutivos con |z| > zsig, a cualquier lado.

    Devuelve BOTH si en esos `length` puntos hay de los dos lados (mezcla) y UP
    o DOWN si todos quedaron del mismo lado (desplazamiento). La señal es la
    misma; solo cambia la descripción.
    """
    up_q = inp.z > zsig + _REL_TOL
    dn_q = inp.z < -zsig - _REL_TOL
    hit = _run_length(up_q | dn_q) >= length
    out = np.zeros(hit.shape, dtype=np.int8)
    out[hit] = BOTH
    out[hit & (_run_length(up_q) >= length)] = UP
    out[hit & (_run_length(dn_q) >= length)] = DOWN
    return out


# --------------------------------------------------------------------------
# Las doce reglas, cada una independiente
# --------------------------------------------------------------------------


def rule_we1(inp: RuleInput) -> np.ndarray:
    """WE1: un punto fuera de los límites de control (Montgomery, tabla 5.1, regla 1)."""
    return beyond_limits(inp)


def rule_we2(inp: RuleInput) -> np.ndarray:
    """WE2: 2 de 3 consecutivos más allá de 2 sigma, mismo lado (tabla 5.1, regla 2)."""
    return k_of_m_beyond(inp, 2, 3, 2.0)


def rule_we3(inp: RuleInput) -> np.ndarray:
    """WE3: 4 de 5 consecutivos más allá de 1 sigma, mismo lado (tabla 5.1, regla 3)."""
    return k_of_m_beyond(inp, 4, 5, 1.0)


def rule_we4(inp: RuleInput) -> np.ndarray:
    """WE4: 8 consecutivos del mismo lado de la línea central (tabla 5.1, regla 4)."""
    return run_same_side(inp, 8)


def rule_n1(inp: RuleInput) -> np.ndarray:
    """Nelson 1: un punto a más de 3 sigma (fuera de los límites)."""
    return beyond_limits(inp)


def rule_n2(inp: RuleInput) -> np.ndarray:
    """Nelson 2: 9 consecutivos del mismo lado de la línea central."""
    return run_same_side(inp, 9)


def rule_n3(inp: RuleInput) -> np.ndarray:
    """Nelson 3: 6 consecutivos estrictamente crecientes o decrecientes."""
    return run_trend(inp, 6)


def rule_n4(inp: RuleInput) -> np.ndarray:
    """Nelson 4: 14 consecutivos alternando subida y bajada (no lados de la LC)."""
    return run_alternating(inp, 14)


def rule_n5(inp: RuleInput) -> np.ndarray:
    """Nelson 5: 2 de 3 consecutivos en zona A o más allá, mismo lado."""
    return k_of_m_beyond(inp, 2, 3, 2.0)


def rule_n6(inp: RuleInput) -> np.ndarray:
    """Nelson 6: 4 de 5 consecutivos en zona B o más allá, mismo lado."""
    return k_of_m_beyond(inp, 4, 5, 1.0)


def rule_n7(inp: RuleInput) -> np.ndarray:
    """Nelson 7: 15 consecutivos en zona C (dentro de 1 sigma), a ambos lados."""
    return run_within(inp, 15, 1.0)


def rule_n8(inp: RuleInput) -> np.ndarray:
    """Nelson 8: 8 consecutivos fuera de la zona C (a más de 1 sigma), cualquier lado."""
    return run_outside(inp, 8, 1.0)


_SIDE = {UP: "por encima", DOWN: "por debajo"}

RULES: dict[str, RuleSpec] = {
    "WE1": RuleSpec("WE1", "Western Electric", False, rule_we1, {
        UP: "Western Electric 1: el punto {p} ({v}) está por encima del límite superior de control ({ucl}).",
        DOWN: "Western Electric 1: el punto {p} ({v}) está por debajo del límite inferior de control ({lcl}).",
    }),
    "WE2": RuleSpec("WE2", "Western Electric", True, rule_we2, {
        s: f"Western Electric 2: 2 de 3 puntos consecutivos más allá de 2 sigma {_SIDE[s]} de la línea central; se completa en el punto {{p}}."
        for s in (UP, DOWN)
    }),
    "WE3": RuleSpec("WE3", "Western Electric", True, rule_we3, {
        s: f"Western Electric 3: 4 de 5 puntos consecutivos más allá de 1 sigma {_SIDE[s]} de la línea central; se completa en el punto {{p}}."
        for s in (UP, DOWN)
    }),
    "WE4": RuleSpec("WE4", "Western Electric", False, rule_we4, {
        s: f"Western Electric 4: 8 puntos consecutivos {_SIDE[s]} de la línea central; se completa en el punto {{p}}."
        for s in (UP, DOWN)
    }),
    "N1": RuleSpec("N1", "Nelson", False, rule_n1, {
        UP: "Nelson 1: el punto {p} ({v}) está por encima del límite superior de control ({ucl}).",
        DOWN: "Nelson 1: el punto {p} ({v}) está por debajo del límite inferior de control ({lcl}).",
    }),
    "N2": RuleSpec("N2", "Nelson", False, rule_n2, {
        s: f"Nelson 2: 9 puntos consecutivos {_SIDE[s]} de la línea central; se completa en el punto {{p}}."
        for s in (UP, DOWN)
    }),
    "N3": RuleSpec("N3", "Nelson", False, rule_n3, {
        UP: "Nelson 3: 6 puntos consecutivos en aumento (tendencia ascendente); se completa en el punto {p}.",
        DOWN: "Nelson 3: 6 puntos consecutivos en descenso (tendencia descendente); se completa en el punto {p}.",
    }),
    "N4": RuleSpec("N4", "Nelson", False, rule_n4, {
        BOTH: "Nelson 4: 14 puntos consecutivos que alternan subiendo y bajando; se completa en el punto {p}. "
              "Sugiere dos fuentes alternadas (máquinas, operarios, proveedores).",
    }),
    "N5": RuleSpec("N5", "Nelson", True, rule_n5, {
        s: f"Nelson 5: 2 de 3 puntos consecutivos en la zona A o más allá, {_SIDE[s]} de la línea central; se completa en el punto {{p}}."
        for s in (UP, DOWN)
    }),
    "N6": RuleSpec("N6", "Nelson", True, rule_n6, {
        s: f"Nelson 6: 4 de 5 puntos consecutivos en la zona B o más allá, {_SIDE[s]} de la línea central; se completa en el punto {{p}}."
        for s in (UP, DOWN)
    }),
    "N7": RuleSpec("N7", "Nelson", True, rule_n7, {
        BOTH: "Nelson 7: 15 puntos consecutivos dentro de 1 sigma de la línea central (zona C); se completa en el punto {p}. "
              "Sugiere estratificación o límites demasiado anchos.",
    }),
    "N8": RuleSpec("N8", "Nelson", True, rule_n8, {
        BOTH: "Nelson 8: 8 puntos consecutivos a más de 1 sigma de la línea central, a ambos lados y sin ninguno en la zona C; "
              "se completa en el punto {p}. Sugiere una mezcla de poblaciones (dos fuentes con medias distintas).",
        **{s: f"Nelson 8: 8 puntos consecutivos a más de 1 sigma {_SIDE[s]} de la línea central, sin ninguno en la zona C; "
              "se completa en el punto {p}. Como todos están del mismo lado, indica un desplazamiento del nivel del "
              "proceso, no dos poblaciones."
           for s in (UP, DOWN)},
    }),
}

ZONE_RULES: tuple[str, ...] = tuple(r for r in RULE_IDS if RULES[r].needs_zones)
NON_ZONE_RULES: tuple[str, ...] = tuple(r for r in RULE_IDS if not RULES[r].needs_zones)


# --------------------------------------------------------------------------
# Preparación y evaluación
# --------------------------------------------------------------------------


def _validate_rule_ids(rules: Iterable[str]) -> list[str]:
    out: list[str] = []
    for r in rules:
        if r not in RULES:
            raise ValueError(f"Regla desconocida: {r!r}. Valores válidos: {', '.join(RULE_IDS)}.")
        if r not in out:
            out.append(r)
    return out


def _resolve_limits(values, center, ucl, lcl, sigma, limit_width):
    x = np.asarray(values, dtype=float)
    c = np.broadcast_to(np.asarray(center, dtype=float), x.shape)
    if sigma is not None:
        s = np.broadcast_to(np.asarray(sigma, dtype=float), x.shape)
    else:
        s = None
    if ucl is None or lcl is None:
        if s is None:
            raise ValueError("Se necesitan los límites (ucl y lcl) o sigma del estadístico.")
        u = c + limit_width * s if ucl is None else np.broadcast_to(np.asarray(ucl, float), x.shape)
        lo = c - limit_width * s if lcl is None else np.broadcast_to(np.asarray(lcl, float), x.shape)
    else:
        u = np.broadcast_to(np.asarray(ucl, dtype=float), x.shape)
        lo = np.broadcast_to(np.asarray(lcl, dtype=float), x.shape)
    return x, c, u, lo, s


def prepare(values, center, *, ucl=None, lcl=None, sigma=None, limit_width: float = 3.0,
            symmetric: Optional[bool] = None) -> tuple[RuleInput, Optional[str]]:
    """Arma la entrada de las reglas. Devuelve (entrada, motivo si no hay zonas).

    - Con `sigma` y sin límites: límites = LC ± L·sigma y zonas simétricas.
    - Con límites y sin `sigma`: sigma = (LCS - LC)/L.
    - `symmetric=None` lo infiere de los límites (LCS - LC == LC - LCI).
    """
    x, c, u, lo, s = _resolve_limits(values, center, ucl, lcl, sigma, limit_width)
    if x.ndim == 1:
        x, c, u, lo = (a[np.newaxis, :] for a in (x, c, u, lo))
        s = None if s is None else s[np.newaxis, :]
    scale = np.maximum(1.0, np.maximum(np.abs(c), np.abs(u)))
    tol = _REL_TOL * scale
    if symmetric is None:
        if sigma is not None and ucl is None and lcl is None:
            symmetric = True
        else:
            symmetric = bool(np.all(np.abs((u - c) - (c - lo)) <= tol))
    reason: Optional[str] = None
    z = None
    if not symmetric:
        reason = ("la distribución del estadístico graficado es asimétrica respecto de la línea central "
                  "(o un límite está truncado en 0), así que las zonas A, B y C no tienen las "
                  "probabilidades de una distribución simétrica y la regla tendría una tasa de falsas "
                  "alarmas distinta de la nominal")
    else:
        sig = s if s is not None else (u - c) / limit_width
        if not np.all(np.isfinite(sig)) or np.any(sig <= tol):
            reason = "la desviación estándar del estadístico es 0, así que las zonas no están definidas"
        else:
            z = (x - c) / sig
    return RuleInput(x=x, center=c, ucl=u, lcl=lo, z=z, tol=tol), reason


def applicable_rules(rules: Iterable[str], zones_available: bool, reason: str = "", *,
                     serially_correlated: bool = False) -> tuple[list[str], dict[str, str]]:
    """Separa las reglas pedidas en aplicables y omitidas (con motivo).

    Con `serially_correlated=True` (panel MR) solo quedan WE1 y N1.
    """
    applied, skipped = [], {}
    for r in _validate_rule_ids(rules):
        if serially_correlated and r not in LIMIT_RULES:
            skipped[r] = f"{r} no se aplica: {SERIAL_CORRELATION_REASON}."
        elif RULES[r].needs_zones and not zones_available:
            skipped[r] = f"{r} no se aplica: {reason or 'las zonas no están definidas'}."
        else:
            applied.append(r)
    return applied, skipped


def _join_ids(ids: Sequence[str]) -> str:
    return ids[0] if len(ids) == 1 else ", ".join(ids[:-1]) + " y " + ids[-1]


def asymmetry_warning(applied: Iterable[str], *, discrete: bool = False) -> Optional[str]:
    """Advertencia para un panel asimétrico según las reglas sin zonas aplicadas.

    Devuelve None si no se aplicó ninguna de WE4, N2, N3 o N4. Con
    `discrete=True` (conteos) no afirma que la tasa de falsas alarmas sea mayor:
    puede ser distinta de la nominal en cualquier sentido.
    """
    applied = list(applied)
    side = [r for r in SIDE_RUN_RULES if r in applied]
    order = [r for r in ORDER_RULES if r in applied]
    if not side and not order:
        return None
    parts = []
    if side:
        one = len(side) == 1
        head = (f"{'la regla' if one else 'las reglas'} {_join_ids(side)} {'se aplicó' if one else 'se aplicaron'} "
                f"aunque {'el gráfico es de conteos con límites asimétricos' if discrete else 'el estadístico graficado es asimétrico'}: "
                "la probabilidad de quedar por encima de la línea central no es 1/2")
        if discrete:
            tail = (", y si la línea central coincide con un valor posible del conteo, los puntos que caen "
                    "exactamente sobre ella cortan la racha. Por eso su tasa de falsas alarmas es distinta de la "
                    "nominal: mayor si la línea central no es un valor posible del conteo y posiblemente mucho "
                    "menor si lo es, con pérdida de sensibilidad. "
                    f"Una señal de {'esta regla' if one else 'estas reglas'} es un indicio a confirmar, no una prueba")
        else:
            tail = (", así que su tasa de falsas alarmas es mayor que la nominal y una señal de "
                    f"{'esta regla' if one else 'estas reglas'} es un indicio a confirmar, no una prueba")
        parts.append(head + tail)
    if order:
        one = len(order) == 1
        lead = "" if side else (
            "el gráfico es de conteos con límites asimétricos; " if discrete else "el estadístico graficado es asimétrico; ")
        parts.append(
            f"{lead}{'la regla' if one else 'las reglas'} {_join_ids(order)} "
            f"{'depende' if one else 'dependen'} solo del orden de los valores, así que la asimetría no "
            "aumenta su tasa de falsas alarmas con datos continuos e independientes (con conteos, los "
            "empates la reducen)"
        )
    parts = [q[0].upper() + q[1:] for q in parts]
    return ". ".join(q.rstrip(".") for q in parts) + "."


def _fmt(v: float) -> str:
    """Número con 6 cifras significativas, coma decimal y sin notación científica."""
    t = f"{v:.6g}"
    if "e" in t or "E" in t:
        if abs(v) >= 1:
            t = f"{v:.0f}"                       # >= 10^6: entero, sin cifras de más
        else:
            decimals = 5 - math.floor(math.log10(abs(v)))
            t = f"{v:.{decimals}f}".rstrip("0").rstrip(".")
    return t.replace(".", ",")


def evaluate_rules(
    values: Sequence[float],
    center,
    *,
    ucl=None,
    lcl=None,
    sigma=None,
    rules: Iterable[str] = ("WE1",),
    limit_width: float = 3.0,
    symmetric: Optional[bool] = None,
    excluded: Iterable[int] = (),
    labels: Optional[Sequence[str]] = None,
    indices: Optional[Sequence[int]] = None,
    serially_correlated: bool = False,
    discrete: bool = False,
) -> RuleOutcome:
    """Evalúa reglas sobre una serie y devuelve las señales con descripción en español.

    Parámetros:
    - values: valores graficados, en orden.
    - center, ucl, lcl, sigma: escalares o arreglos por punto. Basta con
      (center, sigma) o con (center, ucl, lcl).
    - rules: identificadores WE1..WE4, N1..N8.
    - symmetric: False en R, S, MR y atributos truncados; None para inferirlo.
    - excluded: posiciones (en `values`) que no participan en las corridas.
    - labels: etiqueta por posición para el texto (por defecto, posición + 1).
    - indices: índice que se reporta por posición (por defecto, la posición).
      Sirve para el panel MR, cuyo primer valor corresponde al subgrupo 1.
    - serially_correlated: True en el panel MR; solo se aplican WE1 y N1.
    - discrete: True en conteos (p, np, c, u); solo cambia el texto de la advertencia.

    Si los límites no son simétricos y se aplicó WE4, N2, N3 o N4, el
    resultado trae una advertencia en `warnings` (ver `asymmetry_warning`).
    """
    requested = _validate_rule_ids(rules)
    x_all = np.asarray(values, dtype=float)
    if x_all.ndim != 1:
        raise ValueError("evaluate_rules espera una serie unidimensional.")
    m = x_all.shape[0]
    if not np.all(np.isfinite(x_all)):
        raise ValueError("La serie contiene valores no finitos.")
    _, c_all, u_all, l_all, s_all = _resolve_limits(x_all, center, ucl, lcl, sigma, limit_width)

    excl = np.zeros(m, dtype=bool)
    for i in excluded:
        if not 0 <= int(i) < m:
            raise ValueError(f"Índice excluido fuera de rango: {i}.")
        excl[int(i)] = True
    keep = np.flatnonzero(~excl)

    if symmetric is None:
        tol_all = _REL_TOL * np.maximum(1.0, np.maximum(np.abs(c_all), np.abs(u_all)))
        if sigma is not None and ucl is None and lcl is None:
            symmetric = True
        else:
            symmetric = bool(np.all(np.abs((u_all - c_all) - (c_all - l_all)) <= tol_all))

    outcome = RuleOutcome()
    if keep.size == 0:
        outcome.applied, outcome.skipped = applicable_rules(
            requested, True, serially_correlated=serially_correlated)
        return outcome

    inp, reason = prepare(
        x_all[keep], c_all[keep], ucl=u_all[keep], lcl=l_all[keep],
        sigma=None if s_all is None else s_all[keep],
        limit_width=limit_width, symmetric=symmetric,
    )
    applied, skipped = applicable_rules(requested, inp.z is not None, reason or "",
                                        serially_correlated=serially_correlated)
    outcome.applied, outcome.skipped = applied, skipped
    if not symmetric:
        warning = asymmetry_warning(applied, discrete=discrete)
        if warning:
            outcome.warnings.append(warning)

    lab = list(labels) if labels is not None else [str(i + 1) for i in range(m)]
    idx = list(indices) if indices is not None else list(range(m))
    if len(lab) != m or len(idx) != m:
        raise ValueError("labels e indices deben tener el mismo largo que values.")

    found: list[tuple[int, int, Violation]] = []
    for r in applied:
        order = RULE_IDS.index(r)
        spec = RULES[r]
        codes = spec.func(inp)[0]
        for pos_c in np.flatnonzero(codes):
            pos = int(keep[pos_c])
            text = spec.template[int(codes[pos_c])].format(
                p=lab[pos], v=_fmt(x_all[pos]), ucl=_fmt(u_all[pos]), lcl=_fmt(l_all[pos]),
            )
            found.append((idx[pos], order, Violation(rule=r, index=int(idx[pos]), description=text)))
    found.sort(key=lambda t: (t[0], t[1]))
    outcome.violations = [v for _, _, v in found]
    return outcome


def evaluate_limits(values, limits: ControlLimits, rules: Iterable[str], **kwargs) -> RuleOutcome:
    """Atajo: evalúa reglas con un `ControlLimits` (usa su sigma y su simetría)."""
    x = np.asarray(values, dtype=float)
    c, u, lo, s = limits.as_arrays(x.shape[0])
    sig = s if limits.symmetric else None
    kwargs.setdefault("serially_correlated", limits.serially_correlated)
    kwargs.setdefault("discrete", limits.discrete)
    return evaluate_rules(x, c, ucl=u, lcl=lo, sigma=sig, rules=rules,
                          limit_width=limits.limit_width, symmetric=limits.symmetric, **kwargs)


# --------------------------------------------------------------------------
# Versión vectorizada para simulación (ARL)
# --------------------------------------------------------------------------


def signal_matrix(values, center, *, ucl=None, lcl=None, sigma=None,
                  rules: Iterable[str] = ("WE1",), limit_width: float = 3.0,
                  symmetric: Optional[bool] = None) -> np.ndarray:
    """Matriz booleana (réplicas × T): True donde se completa alguna señal.

    `values` es 2D (cada fila una corrida simulada) o 1D. center, sigma, ucl y
    lcl se difunden a la forma de `values`. A diferencia de `evaluate_rules`, si
    una regla pedida necesita zonas y no las hay, lanza ValueError en lugar de
    omitirla en silencio (una simulación con reglas omitidas daría un ARL falso).
    """
    requested = _validate_rule_ids(rules)
    x = np.asarray(values, dtype=float)
    if x.ndim == 1:
        x = x[np.newaxis, :]
    inp, reason = prepare(x, center, ucl=ucl, lcl=lcl, sigma=sigma,
                          limit_width=limit_width, symmetric=symmetric)
    applied, skipped = applicable_rules(requested, inp.z is not None, reason or "")
    if skipped:
        raise ValueError(" ".join(skipped.values()))
    out = np.zeros(inp.x.shape, dtype=bool)
    for r in applied:
        out |= RULES[r].func(inp) != NO_SIGNAL
    return out


def first_signal(values, center, **kwargs) -> np.ndarray:
    """Índice (base 0) de la primera señal por fila; -1 si la fila no señala.

    La longitud de corrida de una fila que señala es `first_signal + 1`.
    """
    sig = signal_matrix(values, center, **kwargs)
    has = sig.any(axis=-1)
    first = np.argmax(sig, axis=-1)
    return np.where(has, first, -1)


__all__ = [
    "RULE_IDS", "WESTERN_ELECTRIC", "NELSON", "ZONE_RULES", "NON_ZONE_RULES", "RULES",
    "LIMIT_RULES", "SIDE_RUN_RULES", "ORDER_RULES", "ASYMMETRY_SENSITIVE_RULES", "SERIAL_CORRELATION_REASON",
    "Violation", "RuleOutcome", "ControlLimits", "RuleInput", "RuleSpec",
    "prepare", "applicable_rules", "asymmetry_warning", "evaluate_rules", "evaluate_limits",
    "signal_matrix", "first_signal",
    "rule_we1", "rule_we2", "rule_we3", "rule_we4",
    "rule_n1", "rule_n2", "rule_n3", "rule_n4", "rule_n5", "rule_n6", "rule_n7", "rule_n8",
    "beyond_limits", "k_of_m_beyond", "run_same_side", "run_trend", "run_alternating",
    "run_within", "run_outside",
]
