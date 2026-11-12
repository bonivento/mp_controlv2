"""Cálculos independientes para validar `app.spc`.

Nada de este archivo importa `app.spc`: cada valor esperado se obtiene por un
camino distinto al del software (otra integral, otra función de scipy, un bucle
explícito en lugar de operaciones vectorizadas, una cadena de Markov o una
simulación propia). Así un error del software no se repite en la prueba.

Lo usan los archivos `test_val_*.py` de esta carpeta y `reporte.py`, que
imprime las tablas de `docs/validacion.md`.
"""

from __future__ import annotations

import itertools
import math
from functools import lru_cache
from typing import Optional, Sequence

import numpy as np
from scipy import integrate, sparse, stats
from scipy.sparse.linalg import spsolve

_phi, _Phi = stats.norm.pdf, stats.norm.cdf


# --------------------------------------------------------------------------
# Constantes por otra integral (no la del software)
# --------------------------------------------------------------------------


@lru_cache(maxsize=None)
def d2_por_maximo(n: int) -> float:
    """d2 = E[R]/σ = 2·E[X(n)] = 2n ∫ x φ(x) Φ(x)^(n-1) dx (densidad del máximo).

    El software integra la forma ∫[1 - Φ^n - (1-Φ)^n]; aquí se usa la esperanza
    del máximo, que es otra expresión (David y Nagaraja, 2003, cap. 3).
    """
    v = integrate.quad(lambda x: x * _phi(x) * _Phi(x) ** (n - 1), -12, 12,
                       epsabs=1e-13, epsrel=1e-13, limit=400)[0]
    return 2 * n * v


def _simpson_weights(m: int, h: float) -> np.ndarray:
    w = np.ones(m)
    w[1:-1:2], w[2:-1:2] = 4.0, 2.0
    return w * h / 3.0


@lru_cache(maxsize=None)
def momentos_del_rango(n: int) -> tuple[float, float]:
    """(E[W], E[W²]) de W = R/σ con la densidad del rango
    f_W(t) = n(n-1) ∫ φ(y-t) φ(y) [Φ(y) - Φ(y-t)]^(n-2) dy  (David y Nagaraja, 2003),
    integrada con Simpson en una malla (y, t) rectangular y suave.
    """
    y = np.linspace(-9.0, 9.0, 1801)
    t = np.linspace(0.0, 14.0, 1401)
    Y, T = np.meshgrid(y, t, indexing="ij")
    f = n * (n - 1) * _phi(Y - T) * _phi(Y) * (_Phi(Y) - _Phi(Y - T)) ** (n - 2)
    wy = _simpson_weights(y.size, y[1] - y[0])
    fw = wy @ f  # densidad del rango en cada t
    wt = _simpson_weights(t.size, t[1] - t[0])
    return float(wt @ (t * fw)), float(wt @ (t * t * fw))


def d3_por_momentos(n: int) -> float:
    """d3 = sd(R)/σ = √(E[W²] - E[W]²) con la densidad del rango (ver `momentos_del_rango`)."""
    e1, e2 = momentos_del_rango(n)
    return math.sqrt(e2 - e1 * e1)


def c4_por_chi(n: int) -> float:
    """c4 = E[S]/σ = E[χ_(n-1)]/√(n-1), con la media de la distribución chi de scipy."""
    return float(stats.chi(n - 1).mean() / math.sqrt(n - 1))


def factores_propios(n: int, L: float = 3.0) -> dict[str, float]:
    """Los catorce factores del apéndice VI desde d2, d3 y c4 propios."""
    c4 = c4_por_chi(n)
    out = {"A": L / math.sqrt(n), "A3": L / (c4 * math.sqrt(n)), "c4": c4}
    s = math.sqrt(1 - c4 * c4)
    out.update(B3=max(0.0, 1 - L * s / c4), B4=1 + L * s / c4, B5=max(0.0, c4 - L * s), B6=c4 + L * s)
    if n <= 25:
        d2, d3 = d2_por_maximo(n), d3_por_momentos(n)
        out.update(d2=d2, d3=d3, A2=L / (d2 * math.sqrt(n)), D1=max(0.0, d2 - L * d3), D2=d2 + L * d3,
                   D3=max(0.0, 1 - L * d3 / d2), D4=1 + L * d3 / d2)
    return out


# --------------------------------------------------------------------------
# Reglas de corrida con bucles explícitos
# --------------------------------------------------------------------------


def reglas_ingenuas(x: Sequence[float], center, sigma, rule: str, ucl=None, lcl=None,
                    excluded: Sequence[int] = ()) -> list[int]:
    """Índices (de la serie original) donde se completa `rule`.

    Definiciones (Montgomery, tabla 5.1; Nelson, 1984), escritas punto a punto:
    los excluidos se quitan antes de evaluar, las ventanas k de m son parciales
    al inicio y una señal k de m se marca en un punto que cumple la condición.
    Comparaciones estrictas, sin tolerancia (usar datos sin empates exactos o
    valores elegidos a mano).
    """
    m = len(x)
    keep = [i for i in range(m) if i not in set(excluded)]
    xs = [float(x[i]) for i in keep]
    cs = [float(np.broadcast_to(center, (m,))[i]) for i in keep]
    ss = [float(np.broadcast_to(sigma, (m,))[i]) for i in keep]
    us = [float(np.broadcast_to(ucl if ucl is not None else np.asarray(center) + 3 * np.asarray(sigma), (m,))[i])
          for i in keep]
    ls = [float(np.broadcast_to(lcl if lcl is not None else np.asarray(center) - 3 * np.asarray(sigma), (m,))[i])
          for i in keep]
    z = [(xs[t] - cs[t]) / ss[t] if ss[t] > 0 else 0.0 for t in range(len(xs))]
    out = []
    for t in range(len(xs)):
        hit = False
        if rule in ("WE1", "N1"):
            hit = xs[t] > us[t] or xs[t] < ls[t]
        elif rule in ("WE2", "N5", "WE3", "N6"):
            k, w, lim = (2, 3, 2.0) if rule in ("WE2", "N5") else (4, 5, 1.0)
            win = range(max(0, t - w + 1), t + 1)
            for sgn in (1, -1):
                if sgn * z[t] > lim and sum(1 for j in win if sgn * z[j] > lim) >= k:
                    hit = True
        elif rule in ("WE4", "N2"):
            L = 8 if rule == "WE4" else 9
            if t >= L - 1:
                seg = range(t - L + 1, t + 1)
                hit = all(xs[j] > cs[j] for j in seg) or all(xs[j] < cs[j] for j in seg)
        elif rule == "N3":
            if t >= 5:
                seg = xs[t - 5:t + 1]
                hit = all(a < b for a, b in zip(seg, seg[1:])) or all(a > b for a, b in zip(seg, seg[1:]))
        elif rule == "N4":
            if t >= 13:
                seg = xs[t - 13:t + 1]
                d = [b - a for a, b in zip(seg, seg[1:])]
                hit = all(v != 0 for v in d) and all(d[i] * d[i + 1] < 0 for i in range(len(d) - 1))
        elif rule == "N7":
            if t >= 14:
                hit = all(abs(z[j]) < 1 for j in range(t - 14, t + 1))
        elif rule == "N8":
            if t >= 7:
                hit = all(abs(z[j]) > 1 for j in range(t - 7, t + 1))
        else:
            raise ValueError(rule)
        if hit:
            out.append(keep[t])
    return out


# --------------------------------------------------------------------------
# Cadenas de Markov para ARL exactos
# --------------------------------------------------------------------------


def arl_racha(p_arriba: float, p_abajo: float, largo: int, p_fuera: float = 0.0) -> float:
    """ARL de "un punto fuera" + "racha de `largo` del mismo lado" con puntos independientes.

    p_fuera: probabilidad de señal inmediata; p_arriba y p_abajo: de caer de cada
    lado sin señal; el resto (1 - suma) cae sobre la línea central y corta la racha.
    """
    k = largo - 1
    size = 1 + 2 * k
    Q = np.zeros((size, size))
    p_sobre = 1.0 - p_fuera - p_arriba - p_abajo
    for s in range(size):
        lado_arriba = 1 <= s <= k
        lado_abajo = s > k
        run = s if lado_arriba else (s - k if lado_abajo else 0)
        # arriba
        nr = run + 1 if lado_arriba else 1
        if nr <= k:
            Q[s, nr] += p_arriba
        # abajo
        nr = run + 1 if lado_abajo else 1
        if nr <= k:
            Q[s, k + nr] += p_abajo
        Q[s, 0] += p_sobre
    return float(np.linalg.solve(np.eye(size) - Q, np.ones(size))[0])


_REGIONS = ("A+", "B+", "C+", "C-", "B-", "A-")


def _region_probs(delta: float) -> dict[str, float]:
    c = lambda a: float(_Phi(a - delta))  # noqa: E731
    return {"A+": c(3) - c(2), "B+": c(2) - c(1), "C+": c(1) - c(0),
            "C-": c(0) - c(-1), "B-": c(-1) - c(-2), "A-": c(-2) - c(-3)}


def arl_western_electric(delta: float) -> float:
    """ARL exacto (estado cero) de WE1 + WE2 + WE3 + WE4 en un gráfico de individuales
    normal con límites de 3σ y desplazamiento `delta` (en σ del estadístico).

    Cadena de Markov al estilo de Champ y Woodall (1987): el estado guarda las
    regiones de los últimos 4 puntos (None al inicio, ventana parcial) y el largo
    de la racha del mismo lado (tope 7). Se construye solo la parte alcanzable.
    """
    probs = _region_probs(delta)

    def side(r):
        return 0 if r is None else (1 if r.endswith("+") else -1)

    start = ((None, None, None, None), 0)
    index = {start: 0}
    rows, cols, vals = [], [], []
    queue = [start]
    while queue:
        st = queue.pop()
        i = index[st]
        last4, run = st
        for r, p in probs.items():
            s = side(r)
            win3 = list(last4[2:]) + [r]
            win5 = list(last4) + [r]
            we2 = r[0] == "A" and sum(1 for q in win3 if q is not None and q[0] == "A" and side(q) == s) >= 2
            we3 = r[0] in "AB" and sum(1 for q in win5 if q is not None and q[0] in "AB" and side(q) == s) >= 4
            nrun = run + 1 if side(last4[3]) == s else 1
            we4 = nrun >= 8
            if we2 or we3 or we4:
                continue
            nst = ((last4[1], last4[2], last4[3], r), min(nrun, 7))
            if nst not in index:
                index[nst] = len(index)
                queue.append(nst)
            rows.append(i)
            cols.append(index[nst])
            vals.append(p)
    N = len(index)
    Q = sparse.csr_matrix((vals, (rows, cols)), shape=(N, N))
    arl = spsolve(sparse.identity(N, format="csr") - Q, np.ones(N))
    return float(arl[0])


def _cola(f: np.ndarray, h: float) -> np.ndarray:
    """∫_u^1 f(v) dv en cada punto medio u_i de la malla (regla del punto medio)."""
    return np.cumsum(f[::-1])[::-1] * h - 0.5 * h * f


def _cabeza(f: np.ndarray, h: float) -> np.ndarray:
    """∫_0^u f(v) dv en cada punto medio u_i."""
    return np.cumsum(f) * h - 0.5 * h * f


def arl_orden_iid(regla: str, M: int = 400, tol: float = 1e-9) -> float:
    """ARL en control de N3 (6 puntos monótonos) o N4 (14 puntos alternados) con
    observaciones i.i.d. continuas, por la ecuación integral en el valor del
    último punto (transformado a uniforme), resuelta por punto fijo en una malla
    de M puntos medios.

    Como N3 y N4 solo dependen del orden, con datos i.i.d. continuos su ARL no
    depende de la distribución: vale igual para individuales normales, R o S.
    Estado: dirección de la última diferencia, largo j de la cadena y valor u
    del último punto; por simetría F^baja_j(u) = F^sube_j(1 - u). Con M = 400
    da 421,58 (N3) y 601,02 (N4); con M = 2 000, 421,60 y 601,01.
    """
    largo = {"N3": 6, "N4": 14}[regla]
    K = largo - 2                       # cadenas de 1 .. largo-2 diferencias no señalan
    h = 1.0 / M
    F = np.zeros((K, M))
    for _ in range(500_000):
        new = np.empty_like(F)
        if regla == "N3":
            baja = _cabeza(F[0][::-1], h)           # baja: nueva racha descendente de 1
            for j in range(1, K + 1):
                sube = _cola(F[j], h) if j < K else 0.0
                new[j - 1] = 1 + sube + baja
        else:
            igual = _cola(F[0], h)                  # vuelve a subir: la alternancia se corta
            for j in range(1, K + 1):
                alterna = _cabeza(F[j][::-1], h) if j < K else 0.0
                new[j - 1] = 1 + igual + alterna
        dif = float(np.max(np.abs(new - F)))
        F = new
        if dif < tol:
            break
    G = 1 + _cola(F[0], h) + _cabeza(F[0][::-1], h)  # después del primer punto
    return float(1 + G.mean())


# --------------------------------------------------------------------------
# Supuestos
# --------------------------------------------------------------------------


def acf_por_fft(x: Sequence[float], max_lag: int) -> np.ndarray:
    """ACF muestral con la autocovarianza calculada por FFT (camino distinto del producto punto)."""
    x = np.asarray(x, float)
    n = x.size
    d = x - x.mean()
    f = np.fft.rfft(d, 2 * n)
    acov = np.fft.irfft(f * np.conj(f))[:n]
    return acov[1:max_lag + 1] / acov[0]


def ljung_box_propio(x: Sequence[float], m: int) -> tuple[float, float]:
    r = acf_por_fft(x, m)
    n = len(x)
    q = n * (n + 2) * sum(r[k - 1] ** 2 / (n - k) for k in range(1, m + 1))
    return float(q), float(stats.chi2.sf(q, m))


def rachas_por_enumeracion(n1: int, n2: int) -> dict[int, float]:
    """Distribución exacta del número de rachas enumerando todas las disposiciones."""
    total = 0
    counts: dict[int, int] = {}
    for pos in itertools.combinations(range(n1 + n2), n1):
        seq = [0] * (n1 + n2)
        for p in pos:
            seq[p] = 1
        r = 1 + sum(1 for a, b in zip(seq, seq[1:]) if a != b)
        counts[r] = counts.get(r, 0) + 1
        total += 1
    return {r: c / total for r, c in counts.items()}


def rachas_valor_p_exacto(n1: int, n2: int, r: int) -> float:
    """Valor p bilateral 2·min(P(R <= r), P(R >= r)) con aritmética racional exacta
    (fracciones de enteros grandes), sin redondeo intermedio. Sirve para tamaños
    donde la enumeración no es posible (por ejemplo, n1 + n2 > 1 000)."""
    from fractions import Fraction
    total = math.comb(n1 + n2, n1)
    lo = hi = 0
    for k in range(2, n1 + n2 + 1):
        if k % 2 == 0:
            j = k // 2
            w = 2 * math.comb(n1 - 1, j - 1) * math.comb(n2 - 1, j - 1)
        else:
            j = (k - 1) // 2
            w = math.comb(n1 - 1, j) * math.comb(n2 - 1, j - 1) + math.comb(n1 - 1, j - 1) * math.comb(n2 - 1, j)
        if k <= r:
            lo += w
        if k >= r:
            hi += w
    return float(min(Fraction(1), 2 * Fraction(min(lo, hi), total)))


def ad_estadistico_propio(x: Sequence[float]) -> float:
    """A² por la forma de la integral discretizada: A² = -n - Σ (2i-1)/n [ln F_i + ln(1 - F_{n+1-i})]
    con F_i = Φ(z_(i)), usando log(cdf) de scipy.special.ndtr (otra función que la del software)."""
    from scipy.special import ndtr
    x = np.sort(np.asarray(x, float))
    n = x.size
    z = (x - x.mean()) / x.std(ddof=1)
    F = ndtr(z)
    i = np.arange(1, n + 1)
    return float(-n - np.sum((2 * i - 1) * (np.log(F) + np.log(1 - F[::-1]))) / n)


def ad_tamano_real(n: int, critico: float, reps: int = 40_000, seed: int = 7) -> float:
    """Proporción de rechazos bajo H0 (normal) con un valor crítico dado, por simulación."""
    rng = np.random.default_rng(seed)
    x = np.sort(rng.standard_normal((reps, n)), axis=1)
    z = (x - x.mean(axis=1, keepdims=True)) / x.std(axis=1, ddof=1, keepdims=True)
    from scipy.special import ndtr
    F = np.clip(ndtr(z), 1e-300, 1 - 1e-16)
    i = np.arange(1, n + 1)
    a2 = -n - np.sum((2 * i - 1) * (np.log(F) + np.log(1 - F[:, ::-1])), axis=1) / n
    return float(np.mean(a2 > critico))


# --------------------------------------------------------------------------
# Muestreo de aceptación
# --------------------------------------------------------------------------


def pa_simple(n: int, c: int, p: float, dist: str = "binomial", N: Optional[int] = None) -> float:
    if dist == "binomial":
        return float(sum(math.comb(n, d) * p ** d * (1 - p) ** (n - d) for d in range(c + 1)))
    if dist == "poisson":
        lam = n * p
        return float(sum(math.exp(-lam) * lam ** d / math.factorial(d) for d in range(c + 1)))
    D = int(round(p * N))
    return float(sum(math.comb(D, d) * math.comb(N - D, n - d) for d in range(min(c, D) + 1)) / math.comb(N, n))


def plan_minimo_fuerza_bruta(aql, ltpd, alpha, beta, dist="binomial", N=None, n_max=2000):
    """Recorre n = 1, 2, ... y para cada n todos los c; devuelve el primer (n, c) que cumple."""
    for n in range(1, n_max + 1):
        for c in range(0, n):
            if pa_simple(n, c, ltpd, dist, N) <= beta and pa_simple(n, c, aql, dist, N) >= 1 - alpha:
                return n, c
    return None


def doble_monte_carlo(n1, c1, r1, n2, c2, p, N, lotes=200_000, seed=3):
    """Simula lotes binomiales con el plan doble: devuelve (Pa, ASN, AOQ, ATI) empíricos."""
    rng = np.random.default_rng(seed)
    d1 = rng.binomial(n1, p, lotes)
    d2 = rng.binomial(n2, p, lotes)
    acc1 = d1 <= c1
    second = (d1 > c1) & (d1 < r1)
    acc2 = second & (d1 + d2 <= c2)
    acc = acc1 | acc2
    asn = n1 + n2 * second.mean()
    # AOQ: defectuosas que salen en la parte no inspeccionada del lote, dividido por N
    # (las defectuosas de la muestra y de los lotes rechazados se reemplazan).
    rest1 = rng.binomial(N - n1, p, lotes)
    rest2 = rng.binomial(N - n1 - n2, p, lotes)
    outgoing = np.where(acc1, rest1, np.where(acc2, rest2, 0))
    aoq = outgoing.mean() / N
    insp = np.where(acc1, n1, np.where(acc2, n1 + n2, N))
    return float(acc.mean()), float(asn), float(aoq), float(insp.mean())
