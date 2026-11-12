"""Validación independiente de sampling.py.

- Plan simple de menor n: búsqueda por fuerza bruta (todos los n y todos los c)
  con probabilidades sumadas a mano, para binomial, Poisson e hipergeométrica.
- Plan doble: Monte Carlo de lotes (aceptación, ASN, AOQ y ATI empíricos).
"""

import math

import numpy as np
import pytest

from app.spc.sampling import defectives_in_lot, design_single_plan, evaluate_double_plan, evaluate_single_plan

from .independiente import doble_monte_carlo, pa_simple, plan_minimo_fuerza_bruta

CASOS = [
    (0.01, 0.06, 0.05, 0.10, "binomial", None),
    (0.01, 0.06, 0.05, 0.10, "poisson", None),
    (0.02, 0.08, 0.05, 0.10, "binomial", None),
    (0.015, 0.10, 0.10, 0.10, "binomial", None),
    (0.03, 0.12, 0.05, 0.05, "binomial", None),
    (0.02, 0.10, 0.05, 0.10, "hypergeometric", 500),
    (0.04, 0.16, 0.05, 0.10, "hypergeometric", 200),
]


@pytest.mark.parametrize("aql, ltpd, a, b, dist, N", CASOS)
def test_plan_de_menor_n_por_fuerza_bruta(aql, ltpd, a, b, dist, N):
    esperado = plan_minimo_fuerza_bruta(aql, ltpd, a, b, dist, N, n_max=400)
    r = design_single_plan(aql, ltpd, a, b, lot_size=N, distribution=dist)
    assert (r.n, r.c) == esperado
    assert r.alpha_actual == pytest.approx(1 - pa_simple(r.n, r.c, aql, dist, N), abs=1e-12)
    assert r.beta_actual == pytest.approx(pa_simple(r.n, r.c, ltpd, dist, N), abs=1e-12)
    assert r.alpha_actual <= a and r.beta_actual <= b


def test_nomograma_89_2_frente_al_exacto_110_3():
    assert 1 - pa_simple(89, 2, 0.01) == pytest.approx(0.0603, abs=1e-4)   # no cumple α = 0.05
    assert pa_simple(89, 2, 0.06) == pytest.approx(0.0919, abs=1e-4)
    assert 1 - pa_simple(110, 3, 0.01) == pytest.approx(0.0250, abs=1e-4)
    assert pa_simple(110, 3, 0.06) == pytest.approx(0.0980, abs=1e-4)
    assert plan_minimo_fuerza_bruta(0.01, 0.06, 0.05, 0.10) == (110, 3)


def test_aoq_ati_aoql_plan_simple():
    N = 10_000
    r = evaluate_single_plan(89, 2, lot_size=N)
    for pt_aoq, pt_ati in zip(r.aoq_curve, r.ati_curve):
        pa = pa_simple(89, 2, pt_aoq.x)
        assert pt_aoq.y == pytest.approx(pa * pt_aoq.x * (N - 89) / N, abs=1e-12)
        assert pt_ati.y == pytest.approx(89 + (1 - pa) * (N - 89), abs=1e-8)
    grid = np.linspace(0, 0.15, 30001)
    aoq = [pa_simple(89, 2, p) * p * (N - 89) / N for p in grid[::10]]
    assert r.aoql == pytest.approx(max(aoq), rel=1e-5)


@pytest.mark.parametrize("p", [0.01, 0.03, 0.06])
def test_plan_doble_contra_monte_carlo(p):
    N = 5000
    r = evaluate_double_plan(50, 1, 4, 100, 3, lot_size=N, aql=p, ltpd=p)
    pa_mc, asn_mc, aoq_mc, ati_mc = doble_monte_carlo(50, 1, 4, 100, 3, p, N, lotes=300_000)
    se = math.sqrt(pa_mc * (1 - pa_mc) / 300_000)
    assert abs((1 - r.alpha_actual) - pa_mc) < 5 * se
    k = min(range(len(r.asn_curve)), key=lambda i: abs(r.asn_curve[i].x - p))
    pk = r.asn_curve[k].x
    pa, asn, aoq, ati = doble_monte_carlo(50, 1, 4, 100, 3, pk, N, lotes=300_000)
    assert r.asn_curve[k].y == pytest.approx(asn, rel=0.01)
    assert r.aoq_curve[k].y == pytest.approx(aoq, rel=0.03, abs=2e-5)
    assert r.ati_curve[k].y == pytest.approx(ati, rel=0.01, abs=2)


def test_redondeo_de_defectuosas_del_lote():
    assert defectives_in_lot([0.05, 0.03, 0.01], 50).tolist() == [3, 2, 1]


def test_redondeo_hipergeometrica_frente_a_aritmetica_decimal():
    """H15, corregido: D = redondeo aritmético de p·N (0.5 hacia arriba) frente a Decimal
    exacto con ROUND_HALF_UP, en 79 992 combinaciones (p de 0.0001 a 0.9999, 8 tamaños de lote)."""
    from decimal import ROUND_HALF_UP, Decimal
    for N in (7, 50, 99, 200, 333, 500, 1000, 2500):
        ps = [round(k / 10000, 4) for k in range(1, 10000)]
        sw = defectives_in_lot(ps, N).tolist()
        ex = [int((Decimal(str(p)) * N).quantize(Decimal(1), rounding=ROUND_HALF_UP)) for p in ps]
        assert sw == ex
