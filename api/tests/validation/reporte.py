"""Imprime las tablas de evidencia de `docs/validacion.md`.

Uso (desde `api/`):  .venv/bin/python -m tests.validation.reporte > /tmp/tablas.md

Cada fila: caso | fuente del esperado | esperado | software | diferencia | veredicto.
Los esperados salen de `independiente.py` o de fórmulas escritas aquí; nunca de
las funciones del software. Semillas fijas: la salida es reproducible.
"""

from __future__ import annotations

import json
import math
import warnings
from pathlib import Path

import numpy as np
from scipy import stats

from app.spc import constants as K
from app.spc import phases
from app.spc.assumptions import (
    _runs_pmf,
    anderson_darling_critical_value,
    anderson_darling_statistic,
    ljung_box_test,
    runs_test,
)
from app.spc.capability import (
    analyze_capability,
    bissell_interval,
    cp_confidence_interval,
    frozen_sigma_dof,
    sigma_dof,
)
from app.spc.design import compute_arl
from app.spc.rules import RULE_IDS, evaluate_rules, first_signal
from app.spc.sampling import design_single_plan, double_plan_probabilities, evaluate_single_plan
from tests.spc.test_attributes import OJ_D, OJ_N, PC_C, PC_N, PCB_C, VAR_D, VAR_N
from tests.spc.test_variables import MORTGAGE, PISTON

from .independiente import (
    ad_tamano_real,
    arl_orden_iid,
    arl_racha,
    arl_western_electric,
    c4_por_chi,
    d2_por_maximo,
    d3_por_momentos,
    doble_monte_carlo,
    ljung_box_propio,
    pa_simple,
    plan_minimo_fuerza_bruta,
    rachas_por_enumeracion,
    reglas_ingenuas,
)

REF = Path(__file__).resolve().parents[3] / "data" / "referencia"
HEAD = "| Caso | Fuente del esperado | Esperado | Software | Diferencia | Veredicto |\n|---|---|---|---|---|---|"


def g(x, d=6):
    if x is None:
        return "null"
    if isinstance(x, (list, tuple)):
        return "[" + ", ".join(g(v, d) for v in x) + "]"
    return f"{x:.{d}g}"


def row(caso, fuente, esp, sw, tol=None, ok=None, d=6):
    if ok is None:
        diff = abs(float(esp) - float(sw))
        ok = diff <= tol
        dtxt = f"{diff:.1e}"
    else:
        dtxt = "—"
    print(f"| {caso} | {fuente} | {g(esp, d) if not isinstance(esp, str) else esp} | "
          f"{g(sw, d) if not isinstance(sw, str) else sw} | {dtxt} | {'correcto' if ok else '**ERROR**'} |")


def constantes():
    print("\n### Constantes (n = 2 a 25)\n")
    print("| n | d2 propio | d2 software | d3 propio | d3 software | c4 propio | c4 software | máx. dif. | Veredicto |")
    print("|---|---|---|---|---|---|---|---|---|")
    for n in range(2, 26):
        a, b, c = d2_por_maximo(n), d3_por_momentos(n), c4_por_chi(n)
        m = max(abs(a - K.d2(n)), abs(b - K.d3(n)), abs(c - K.c4(n)))
        print(f"| {n} | {a:.7f} | {K.d2(n):.6f} | {b:.7f} | {K.d3(n):.6f} | {c:.7f} | {K.c4(n):.7f} | "
              f"{m:.1e} | {'correcto' if m < 6e-7 else '**ERROR**'} |")


def graficos():
    print("\n### Gráficos por variables y atributos\n")
    print(HEAD)
    d2_5, d3_5, d2_2, d3_2 = d2_por_maximo(5), d3_por_momentos(5), d2_por_maximo(2), d3_por_momentos(2)
    x = np.array(PISTON)
    xbb, rbar = x.mean(), np.ptp(x, axis=1).mean()
    r = phases.phase_one("xbar_r", PISTON)
    row("Anillos de pistón, LCS X-barra", "x̿ + 3R̄/(d2√5), d2 propio", xbb + 3 * rbar / (d2_5 * 5 ** .5), r.charts[0].ucl[0], 1e-8)
    row("Anillos de pistón, LCS R", "R̄(1 + 3d3/d2)", rbar * (1 + 3 * d3_5 / d2_5), r.charts[1].ucl[0], 1e-8)
    s = x.std(axis=1, ddof=1).mean()
    c4 = c4_por_chi(5)
    r = phases.phase_one("xbar_s", PISTON)
    row("Anillos de pistón, LCS S", "S̄(1 + 3√(1-c4²)/c4)", s * (1 + 3 * math.sqrt(1 - c4 * c4) / c4), r.charts[1].ucl[0], 1e-10)
    m = np.array(MORTGAGE, float)
    mrb = np.abs(np.diff(m)).mean()
    r = phases.phase_one("i_mr", MORTGAGE)
    row("Hipotecas, LCS I", "x̄ + 3MR̄/d2(2)", m.mean() + 3 * mrb / d2_2, r.charts[0].ucl[0], 1e-5)
    row("Hipotecas, LCS MR", "MR̄(1 + 3d3/d2)", mrb * (1 + 3 * d3_2 / d2_2), r.charts[1].ucl[0], 1e-5)
    pb = sum(OJ_D) / 1500
    r = phases.phase_one("p", OJ_D, OJ_N)
    row("Jugo de naranja, LCS p", "p̄ + 3√(p̄(1-p̄)/50)", pb + 3 * math.sqrt(pb * (1 - pb) / 50), r.charts[0].ucl[0], 1e-12)
    row("Jugo de naranja, fuera", "conteo a mano", "[14, 22]", g(r.out_of_control_points), ok=r.out_of_control_points == [14, 22])
    rv = phases.phase_one("p", OJ_D, OJ_N, excluded=[(14, "a"), (22, "b")])
    pb2 = 301 / 1400
    row("Jugo, límites revisados (sin 15 y 23)", "p̄ = 301/1400", pb2 + 3 * math.sqrt(pb2 * (1 - pb2) / 50), rv.charts[0].ucl[0], 1e-12)
    row("Jugo, revisado: señal", "conteo a mano", "[20]", g(rv.out_of_control_points), ok=rv.out_of_control_points == [20])
    cb = sum(PCB_C) / 26
    r = phases.phase_one("c", PCB_C)
    row("Tarjetas de circuito, LCS c", "c̄ + 3√c̄", cb + 3 * math.sqrt(cb), r.charts[0].ucl[0], 1e-12)
    u = sum(PC_C) / sum(PC_N)
    r = phases.phase_one("u", PC_C, PC_N)
    row("Computadores, LCI u", "ū - 3√(ū/5)", u - 3 * math.sqrt(u / 5), r.charts[0].lcl[0], 1e-12)
    pv = 234 / 2450
    r = phases.phase_one("p", VAR_D, VAR_N)
    row("p con n variable, LCS muestra 11 (n = 110)", "p̄ + 3√(p̄(1-p̄)/110)", pv + 3 * math.sqrt(pv * (1 - pv) / 110), r.charts[0].ucl[10], 1e-12)
    for name, chart in (("xbar_r_n3.json", "xbar_r"), ("xbar_s_n3.json", "xbar_s")):
        j = json.loads((REF / name).read_text(encoding="utf-8"))
        sg = [s["x"] for s in j["datos"]["subgrupos"]]
        r = phases.phase_one(chart, sg)
        row(f"data/referencia/{name}, LCS X-barra", "JSON (constantes a 3 decimales)", j["esperado"]["ucl_xbar"], r.charts[0].ucl[0], 1e-3)
    j = json.loads((REF / "p.json").read_text(encoding="utf-8"))
    mm = j["datos"]["muestras"]
    r = phases.phase_one("p", [s["defectuosos"] for s in mm], [s["n"] for s in mm])
    row("data/referencia/p.json, LCS n = 80", "fórmula exacta (el JSON dice 0.1436922)", 0.0625 + 3 * math.sqrt(0.0625 * 0.9375 / 80), r.charts[0].ucl[4], 1e-12)
    j = json.loads((REF / "np.json").read_text(encoding="utf-8"))
    r = phases.phase_one("np", j["datos"]["defectuosos"], [100] * 5)
    row("data/referencia/np.json, LCS", "fórmula exacta (el JSON dice 14.04849)", 6.6 + 3 * math.sqrt(6.6 * 0.934), r.charts[0].ucl[0], 1e-12)
    p1 = phases.phase_one("xbar_s", PISTON)
    mu, sg_ = p1.limits.params["mu"], p1.limits.params["sigma"]
    p2 = phases.phase_two("xbar_s", [row_[:4] + [row_[0]] * 4 for row_ in PISTON], p1.limits)
    c8 = c4_por_chi(8)
    row("Fase II con n = 8 (Fase I n = 5), LC S", "c4(8)·σ congelada", c8 * sg_, p2.charts[1].center[0], 1e-12)


def reglas():
    print("\n### Reglas de corrida\n")
    print(HEAD)
    rng = np.random.default_rng(20261111)
    total = diff = 0
    for rep in range(300):
        m = int(rng.integers(5, 70))
        x = [rng.normal(0, 1.2, m), np.cumsum(rng.normal(0, .4, m)), 1.5 * (-1.0) ** np.arange(m) + rng.normal(0, .05, m),
             rng.normal(0, .3, m)][rep % 4]
        excl = sorted(set(rng.integers(0, m, int(rng.integers(0, 4))).tolist())) if rep % 2 else []
        for r in RULE_IDS:
            total += 1
            sw = [v.index for v in evaluate_rules(x, 0.0, sigma=1.0, rules=[r], excluded=excl).violations]
            diff += sw != reglas_ingenuas(x, 0.0, 1.0, r, excluded=excl)
    row(f"{total} evaluaciones (300 series × 12 reglas, con y sin excluidos)", "bucles explícitos (independiente.py)",
        "0 diferencias", f"{diff} diferencias", ok=diff == 0)
    pa = 1 - stats.norm.cdf(3)
    row("ARL0 WE1-WE4, individuales", "cadena de Markov propia", arl_western_electric(0.0),
        compute_arl("individuals", rules=["WE1", "WE2", "WE3", "WE4"], max_runs=8000, seed=7).arl0, 3.0, d=5)
    row("ARL1 WE1-WE4, δ = 1", "cadena de Markov propia", arl_western_electric(1.0),
        compute_arl("individuals", rules=["WE1", "WE2", "WE3", "WE4"], shifts=[1.0], max_runs=8000, seed=7).rows[0].arl1, 0.3, d=5)
    row("ARL0 WE1+WE4, individuales", "cadena de rachas propia", arl_racha(0.5 - pa, 0.5 - pa, 8, 2 * pa),
        compute_arl("individuals", rules=["WE1", "WE4"], max_runs=8000, seed=3).arl0, 6.0, d=5)
    # duda 1
    print("\nARL en control de reglas de racha en paneles asimétricos (duda 1):\n")
    print("| Panel | Regla | ARL0 si P(arriba de la LC) = 0.5 | ARL0 real | Método |\n|---|---|---|---|---|")
    from scipy import integrate

    def cdf_r(w, n):
        return integrate.quad(lambda z: n * stats.norm.pdf(z) * (stats.norm.cdf(z + w) - stats.norm.cdf(z)) ** (n - 1), -12, 12)[0]
    for n in (2, 5, 10):
        b = cdf_r(K.d2(n), n)
        print(f"| R, n = {n} | WE4 | 255 | {arl_racha(1 - b, b, 8):.1f} | cadena propia, P(R > R̄) = {1 - b:.4f} |")
    print(f"| R, n = 2 | N2 | 511 | {arl_racha(1 - cdf_r(K.d2(2), 2), cdf_r(K.d2(2), 2), 9):.1f} | cadena propia |")
    rng = np.random.default_rng(11)
    x = rng.standard_normal((6000, 3001))
    mr = np.abs(np.diff(x, axis=1))
    d2 = K.d2(2)
    for rule, ref in (("WE4", "255"), ("N2", "511"), ("N3", "421.6 (exacto, datos independientes)"), ("N4", "601.0 (exacto, datos independientes)")):
        fs = first_signal(mr, d2, ucl=K.D4(2) * d2, lcl=0.0, rules=[rule], symmetric=False)
        cens = int((fs < 0).sum())
        val = np.mean(np.where(fs >= 0, fs + 1, 3000))
        print(f"| MR | {rule} | {ref} | {val:.0f}{' (≥, ' + str(cens) + ' censuradas)' if cens else ''} | simulación, 6000 corridas |")
    n3, n4 = arl_orden_iid("N3"), arl_orden_iid("N4")
    print(f"| cualquier panel continuo i.i.d. (I, R, S) | N3 | {n3:.1f} (exacto) | {n3:.1f} | ecuación integral propia; no depende de la distribución |")
    print(f"| cualquier panel continuo i.i.d. (I, R, S) | N4 | {n4:.1f} (exacto) | {n4:.1f} | ecuación integral propia |")
    for name, up, dn in (("c, c̄ = 2 (LC entera)", stats.poisson.sf(2, 2), stats.poisson.cdf(1, 2)),
                         ("c, c̄ = 4 (LC entera)", stats.poisson.sf(4, 4), stats.poisson.cdf(3, 4)),
                         ("p, n = 100, p̄ = 0.01 (n·p̄ = 1)", stats.binom.sf(1, 100, .01), stats.binom.cdf(0, 100, .01))):
        print(f"| {name} | WE4 | 255 | {arl_racha(up, dn, 8):.1f} | cadena propia; P(sobre la LC) = {1 - up - dn:.3f} corta la racha |")
    for pbar in (0.0098, 0.0102):
        c = 100 * pbar  # no entero: ningún conteo cae sobre la LC
        up = stats.binom.sf(math.floor(c), 100, pbar)
        dn = stats.binom.cdf(math.ceil(c) - 1, 100, pbar)
        print(f"| p, n = 100, p̄ = {pbar} | WE4 | 255 | {arl_racha(up, dn, 8):.1f} | cadena propia, "
              f"P(D > n·p̄) = {up:.3f} (D = 1 queda {'debajo' if c > 1 else 'arriba'} de la LC) |")


def supuestos():
    print("\n### Supuestos\n")
    print(HEAD)
    rng = np.random.default_rng(4)
    y = np.cumsum(rng.normal(size=120)) * 0.3 + rng.normal(size=120)
    q, p = ljung_box_propio(y, 20)
    t = ljung_box_test(y, 20)
    row("Ljung-Box, Q (n = 120, m = 20)", "ACF por FFT, fórmula propia", q, t.statistic, 1e-9)
    row("Ljung-Box, p", "χ²(20) de la Q propia", p, t.p_value, 1e-12)
    mx = max(abs(_runs_pmf(a, b)[r] - v) for a in range(1, 9) for b in range(1, 9) for r, v in rachas_por_enumeracion(a, b).items())
    row("Rachas, pmf exacta (n1, n2 ≤ 8)", "enumeración de las C(n1+n2, n1) disposiciones", 0.0, mx, 1e-14)
    pmf = _runs_pmf(31, 31)
    ex = min(1, 2 * min(sum(v for r, v in pmf.items() if r <= 24), sum(v for r, v in pmf.items() if r >= 24)))
    seq = []
    sizes = [20] + [1] * 11
    u = d = 0
    for a in sizes:
        seq += [10 + .01 * (u + i) for i in range(a)]
        u += a
        seq += [-10 - .01 * (d + i) for i in range(a)]
        d += a
    row("Rachas n1 = n2 = 31, R = 24: valor p", "distribución exacta", ex, runs_test(seq).p_value, 0.005, d=4)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        z = rng.normal(size=50)
        row("Anderson-Darling, A² (n = 50)", "fórmula con scipy.special.ndtr", stats.anderson(z, "norm").statistic,
            anderson_darling_statistic(z), 1e-10)
    for n in (8, 15, 30, 100):
        c, _ = anderson_darling_critical_value(n, 0.05)
        real = ad_tamano_real(n, c, reps=60_000)
        row(f"Anderson-Darling, tamaño real con α = 0.05, n = {n}", "simulación bajo H0 (60 000 réplicas)", 0.05, real, 0.0045, d=4)
    c, _ = anderson_darling_critical_value(3, 0.05)
    row("Anderson-Darling, valor crítico n = 3", "debe ser > 0", "> 0", g(c, 4), ok=c > 0)


def capacidad():
    print("\n### Capacidad\n")
    print(HEAD)
    lo, hi = cp_confidence_interval(2.29, 20)
    row("IC de Cp, Ĉp = 2.29, n = 20: inferior", "2.29·√(χ²_{0.025,19}/19)", 2.29 * math.sqrt(stats.chi2.ppf(.025, 19) / 19), lo, 1e-12, d=4)
    lo, hi = bissell_interval(1.33, 20)
    se = math.sqrt(1 / (9 * 20) + 1.33 ** 2 / 38)
    row("IC de Bissell, Ĉpk = 1.33, n = 20: inferior", "1.33 - z·√(1/(9n) + Ĉ²/(2(n-1)))", 1.33 - stats.norm.isf(.025) * se, lo, 1e-12, d=4)
    rng = np.random.default_rng(42)
    lim = {"chart_type": "xbar_r", "subgroup_size": 5, "sigma_method": "rbar_d2", "points_used": 25,
           "params": {"mu": 0.0, "sigma": 1.0}}
    casos = (("desviación muestral, N = 125", lambda: rng.standard_normal(125).std(ddof=1), 125, None),
             ("R̄/d2, 25 subgrupos de 5", lambda: np.ptp(rng.standard_normal((25, 5)), axis=1).mean() / K.d2(5), 125,
              sigma_dof([[0.0] * 5] * 25, "rbar_d2")),
             ("MR̄/d2, N = 50", lambda: np.abs(np.diff(rng.standard_normal(50))).mean() / K.d2(2), 50,
              sigma_dof([[0.0]] * 50, "mrbar_d2")),
             ("σ congelada (Fase I 25×5), N = 500 nuevos",
              lambda: np.ptp(rng.standard_normal((25, 5)), axis=1).mean() / K.d2(5), 500, frozen_sigma_dof(lim)))
    for name, gen, N, nu in casos:
        hits = hits_nm1 = 0
        for _ in range(6000):
            s = gen()
            a, b = cp_confidence_interval(8 / (6 * s), N, dof=nu)
            hits += a <= 8 / 6 <= b
            a, b = cp_confidence_interval(8 / (6 * s), N)
            hits_nm1 += a <= 8 / 6 <= b
        nu_txt = f"ν = {nu:.1f}" if nu is not None else "ν = N - 1"
        row(f"Cobertura real del IC 95 % de Cp, {name} ({nu_txt}; con ν = N - 1: {hits_nm1 / 6000:.3f})",
            "simulación (6000 réplicas, normal)", 0.95, hits / 6000, 0.012, d=3)
    try:
        analyze_capability(rng.normal(10, .2, (25, 5)).tolist(), lsl=float("nan"), usl=10.7)
        row("LSL = NaN", "debe rechazarse", "ValueError", "aceptado", ok=False)
    except ValueError as e:
        row("LSL = NaN", "debe rechazarse", "ValueError", f"ValueError: {e}", ok=True)


def diseno():
    print("\n### ARL y ATS\n")
    print(HEAD)
    r = compute_arl("xbar", n=5, shifts=[1.0], sampling_interval=0.5)
    row("ARL0, L = 3", "1/(2Φ(-3))", 1 / (2 * stats.norm.sf(3)), r.arl0, 1e-9, d=6)
    b = stats.norm.cdf(3 - 5 ** .5) - stats.norm.cdf(-3 - 5 ** .5)
    row("ARL1, n = 5, δ = 1", "1/(1 - β), β = Φ(3-√5) - Φ(-3-√5)", 1 / (1 - b), r.rows[0].arl1, 1e-9)
    row("ATS1, h = 0.5", "ARL1·h", 0.5 / (1 - b), r.rows[0].ats1, 1e-9)
    r = compute_arl("p", n=50, p0=0.2, p1=[0.3])
    a = 1 - (stats.binom.cdf(18, 50, .2) - stats.binom.cdf(1, 50, .2))
    row("ARL0 real del gráfico p (n = 50, p0 = 0.2)", "1/[1 - P(2 ≤ D ≤ 18)]", 1 / a, r.arl0, 1e-9)
    r = compute_arl("c", c0=4.0, c1=[8.0])
    row("ARL0 real del gráfico c (c0 = 4, LCS = 10 exacto)", "1/P(X ≥ 11)", 1 / stats.poisson.sf(10, 4), r.arl0, 1e-6)
    sim = compute_arl("xbar", n=5, force_simulation=True, max_runs=8000, seed=5)
    row("ARL0 simulado (solo WE1) frente al exacto", "370.398 ± 4 EE", 1 / (2 * stats.norm.sf(3)), sim.arl0, 4 * sim.arl0_std_error, d=5)


def muestreo():
    print("\n### Muestreo de aceptación\n")
    print(HEAD)
    for aql, ltpd, a, b, dist, N in ((0.01, 0.06, .05, .10, "binomial", None), (0.01, 0.06, .05, .10, "poisson", None),
                                     (0.02, 0.10, .05, .10, "hypergeometric", 500), (0.03, 0.12, .05, .05, "binomial", None)):
        bf = plan_minimo_fuerza_bruta(aql, ltpd, a, b, dist, N, n_max=400)
        r = design_single_plan(aql, ltpd, a, b, lot_size=N, distribution=dist)
        row(f"Plan simple AQL {aql}, LTPD {ltpd}, α {a}, β {b}, {dist}{'' if N is None else f', N = {N}'}",
            "fuerza bruta sobre todos los (n, c)", str(bf), str((r.n, r.c)), ok=bf == (r.n, r.c))
    r = evaluate_single_plan(89, 2, aql=0.01, ltpd=0.06)
    row("Plan del nomograma (89, 2): α real", "1 - Σ_{d≤2} C(89,d)0.01^d 0.99^(89-d)", 1 - pa_simple(89, 2, .01), r.alpha_actual, 1e-12, d=4)
    row("Plan del nomograma (89, 2): β real", "Σ_{d≤2} C(89,d)0.06^d 0.94^(89-d)", pa_simple(89, 2, .06), r.beta_actual, 1e-12, d=4)
    pa1, pa2, p2 = (float(v[0]) for v in double_plan_probabilities(50, 1, 4, 100, 3, 0.05))
    mc = doble_monte_carlo(50, 1, 4, 100, 3, 0.05, 5000, lotes=400_000)
    row("Plan doble (50, 1, 4, 100, 3), Pa(0.05)", "Monte Carlo, 400 000 lotes", mc[0], pa1 + pa2, 0.003, d=4)
    row("Plan doble, ASN(0.05)", "Monte Carlo", mc[1], 50 + 100 * p2, 0.3, d=4)


if __name__ == "__main__":
    constantes()
    graficos()
    reglas()
    supuestos()
    capacidad()
    diseno()
    muestreo()
