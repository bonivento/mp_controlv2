"""Pruebas de muestreo de aceptación por atributos.

Casos de libro (Montgomery, *Introduction to Statistical Quality Control*, cap. 15):
- Plan simple n = 89, c = 2: Pa(0.01) = 0.9397; con N = 10 000,
  AOQ(0.01) = 0.0093 y ATI(0.01) = 687.
- El nomograma binomial para AQL = 0.01, α = 0.05, LTPD = 0.06, β = 0.10
  propone n = 89, c = 2. Calculado exacto, ese plan da α ≈ 0.060 y
  β ≈ 0.092 (no cumple α). El menor plan que cumple ambos riesgos es
  n = 110, c = 3.
- Plan doble n1 = 50, c1 = 1, n2 = 100, c2 = 3 (r1 = c2 + 1 = 4) con
  p = 0.05: Pa^I = 0.279, Pa^II = 0.011, Pa = 0.290.
"""

from dataclasses import asdict

import numpy as np
import pytest
from scipy import stats

from app.schemas.sampling import DoublePlanResponse, SinglePlanResponse
from app.spc.sampling import (
    design_single_plan,
    double_plan_probabilities,
    evaluate_double_plan,
    evaluate_single_plan,
    find_single_plan,
    prob_accept,
)


# --------------------------------------------------------------- plan simple


def test_design_finds_smallest_plan_not_the_nomograph_one():
    r = design_single_plan(aql=0.01, ltpd=0.06, alpha=0.05, beta=0.10)
    assert (r.n, r.c) == (110, 3)
    assert r.alpha_actual == pytest.approx(1 - stats.binom.cdf(3, 110, 0.01))
    assert r.alpha_actual <= 0.05 and r.beta_actual <= 0.10
    text = " ".join(r.interpretation.findings)
    # Explica por qué no sirve c = 2. El nomograma solo se menciona si el
    # usuario envía su lectura como plan de referencia (hallazgo H8).
    assert "c = 2" in text and "nomograma" not in text
    ref = design_single_plan(aql=0.01, ltpd=0.06, alpha=0.05, beta=0.10, reference_plan=(89, 2))
    ref_text = [f for f in ref.interpretation.findings if "Plan de referencia" in f][0]
    assert "n = 89, c = 2" in ref_text and "nomograma" in ref_text and "0,06031" in ref_text


def test_no_smaller_plan_meets_both_risks_brute_force():
    for n in range(1, 110):
        c = np.arange(0, n)
        alpha_ok = stats.binom.cdf(c, n, 0.01) >= 0.95
        beta_ok = stats.binom.cdf(c, n, 0.06) <= 0.10
        assert not np.any(alpha_ok & beta_ok), n


def test_nomograph_plan_89_2_does_not_meet_alpha():
    r = evaluate_single_plan(89, 2, aql=0.01, ltpd=0.06, alpha=0.05, beta=0.10)
    assert r.alpha_actual == pytest.approx(0.060, abs=0.0005)
    assert r.beta_actual == pytest.approx(0.092, abs=0.0005)
    assert any("α real" in w for w in r.interpretation.warnings)
    d = design_single_plan(0.01, 0.06, 0.05, 0.10, reference_plan=(89, 2))
    ref = [f for f in d.interpretation.findings if "Plan de referencia" in f][0]
    assert "n = 89, c = 2" in ref and "No cumple" in ref


def test_plan_89_2_montgomery_aoq_and_ati():
    r = evaluate_single_plan(89, 2, lot_size=10_000, aql=0.01)
    pa = stats.binom.cdf(2, 89, 0.01)
    assert pa == pytest.approx(0.9397, abs=1e-4)
    aoq = pa * 0.01 * (10_000 - 89) / 10_000
    assert aoq == pytest.approx(0.0093, abs=1e-4)
    ati = 89 + (1 - pa) * (10_000 - 89)
    assert ati == pytest.approx(687, abs=1)
    # Las curvas devuelven esos mismos valores en p = 0.01 (interpolando).
    xs = [p.x for p in r.ati_curve]
    assert np.interp(0.01, xs, [p.y for p in r.ati_curve]) == pytest.approx(ati, rel=0.02)
    assert np.interp(0.01, xs, [p.y for p in r.aoq_curve]) == pytest.approx(aoq, rel=0.02)


def test_aoql_is_the_maximum_of_aoq():
    r = evaluate_single_plan(89, 2, lot_size=10_000)
    p = np.linspace(0, 0.2, 200_001)
    aoq = stats.binom.cdf(2, 89, p) * p * (10_000 - 89) / 10_000
    assert r.aoql == pytest.approx(aoq.max(), rel=1e-6)
    assert r.aoql_at == pytest.approx(p[np.argmax(aoq)], abs=1e-4)


def test_oc_curve_properties():
    r = evaluate_single_plan(50, 1)
    assert r.oc_curve[0].x == 0.0 and r.oc_curve[0].y == pytest.approx(1.0)
    ys = [pt.y for pt in r.oc_curve]
    assert all(a >= b - 1e-12 for a, b in zip(ys, ys[1:]))
    assert ys[-1] < 0.01
    assert r.ati_curve is None and r.alpha_actual is None and r.beta_actual is None


def test_poisson_and_hypergeometric_designs_are_minimal():
    rp = design_single_plan(0.01, 0.06, distribution="poisson")
    assert stats.poisson.cdf(rp.c, rp.n * 0.01) >= 0.95
    assert stats.poisson.cdf(rp.c, rp.n * 0.06) <= 0.10
    N = 500
    rh = design_single_plan(0.02, 0.10, lot_size=N, distribution="hypergeometric")
    D1, D2 = round(0.02 * N), round(0.10 * N)
    assert stats.hypergeom.cdf(rh.c, N, D1, rh.n) >= 0.95
    assert stats.hypergeom.cdf(rh.c, N, D2, rh.n) <= 0.10
    for n in range(1, rh.n):
        c = np.arange(0, n)
        ok = (stats.hypergeom.cdf(c, N, D1, n) >= 0.95) & (stats.hypergeom.cdf(c, N, D2, n) <= 0.10)
        assert not ok.any()
    assert rh.ati_curve is not None
    assert any("redondeo" in w for w in rh.interpretation.warnings)


def test_prob_accept_distributions_agree_for_small_p():
    p = 0.01
    b = float(prob_accept(200, 3, p, "binomial"))
    po = float(prob_accept(200, 3, p, "poisson"))
    h = float(prob_accept(200, 3, p, "hypergeometric", lot_size=100_000))
    assert b == pytest.approx(po, abs=0.01)
    assert b == pytest.approx(h, abs=0.005)


def test_invalid_sampling_inputs():
    with pytest.raises(ValueError):
        find_single_plan(0.06, 0.01)
    with pytest.raises(ValueError):
        design_single_plan(0.01, 0.06, distribution="hypergeometric")
    with pytest.raises(ValueError):
        evaluate_single_plan(5, 5)
    with pytest.raises(ValueError):
        evaluate_single_plan(200, 2, lot_size=100)


# ---------------------------------------------------------------- plan doble


def test_double_plan_montgomery_ch15():
    pa1, pa2, p2 = (float(v[0]) for v in double_plan_probabilities(50, 1, 4, 100, 3, 0.05))
    assert pa1 == pytest.approx(0.279, abs=0.001)
    assert pa2 == pytest.approx(0.011, abs=0.001)
    assert pa1 + pa2 == pytest.approx(0.290, abs=0.001)
    # A mano: Pa^II = P(d1=2)P(d2<=1) + P(d1=3)P(d2=0), P(segunda) = P(d1=2) + P(d1=3).
    b = stats.binom
    expected2 = b.pmf(2, 50, 0.05) * b.cdf(1, 100, 0.05) + b.pmf(3, 50, 0.05) * b.pmf(0, 100, 0.05)
    assert pa2 == pytest.approx(expected2)
    assert p2 == pytest.approx(b.pmf(2, 50, 0.05) + b.pmf(3, 50, 0.05))


def test_double_plan_curves_asn_ati():
    N = 5000
    r = evaluate_double_plan(50, 1, 4, 100, 3, lot_size=N, aql=0.01, ltpd=0.06)
    i = min(range(len(r.oc_curve)), key=lambda k: abs(r.oc_curve[k].x - 0.05))
    p = r.oc_curve[i].x
    pa1, pa2, p2 = (float(v[0]) for v in double_plan_probabilities(50, 1, 4, 100, 3, p))
    assert r.oc_curve[i].y == pytest.approx(pa1 + pa2)
    assert r.first_sample_accept_curve[i].y == pytest.approx(pa1)
    assert r.asn_curve[i].y == pytest.approx(50 + 100 * p2)
    ati = 50 * pa1 + 150 * pa2 + N * (1 - pa1 - pa2)
    assert r.ati_curve[i].y == pytest.approx(ati)
    aoq = p * (pa1 * (N - 50) + pa2 * (N - 150)) / N
    assert r.aoq_curve[i].y == pytest.approx(aoq)
    assert r.aoql >= max(pt.y for pt in r.aoq_curve) - 1e-12
    assert r.alpha_actual == pytest.approx(1 - sum(float(v[0]) for v in double_plan_probabilities(50, 1, 4, 100, 3, 0.01)[:2]))


def test_double_plan_validation_and_warning():
    with pytest.raises(ValueError):
        evaluate_double_plan(50, 3, 4, 100, 2)  # c2 < c1
    with pytest.raises(ValueError):
        evaluate_double_plan(50, 1, 1, 100, 3)  # r1 <= c1
    r = evaluate_double_plan(50, 1, 6, 100, 3)
    assert any("r1 = c2 + 1" in w for w in r.interpretation.warnings)


# ------------------------------------------------------------------ contrato


def test_sampling_results_convert_to_contract():
    SinglePlanResponse.model_validate(asdict(design_single_plan(0.01, 0.06)))
    SinglePlanResponse.model_validate(asdict(evaluate_single_plan(89, 2, lot_size=10_000, aql=0.01, ltpd=0.06)))
    SinglePlanResponse.model_validate(
        asdict(design_single_plan(0.02, 0.10, lot_size=500, distribution="hypergeometric"))
    )
    DoublePlanResponse.model_validate(asdict(evaluate_double_plan(50, 1, 4, 100, 3, lot_size=5000, aql=0.01)))


def test_hypergeometric_rounding_half_up_and_reported():
    """D = floor(p·N + 0.5), no el redondeo al par de np.rint (hallazgo H15):
    0.05·50 = 2.5 -> 3, 0.03·50 = 1.5 -> 2, 0.07·50 = 3.5 -> 4 (a mano)."""
    from app.spc.sampling import defectives_in_lot

    assert defectives_in_lot([0.05, 0.03, 0.07, 0.01, 0.0], 50).tolist() == [3, 2, 4, 1, 0]
    r = evaluate_single_plan(10, 0, lot_size=50, aql=0.05, ltpd=0.07, distribution="hypergeometric")
    assert r.alpha_actual == pytest.approx(1 - stats.hypergeom.cdf(0, 50, 3, 10))
    assert any("AQL = 5,00 % da D = 3" in w and "LTPD = 7,00 % da D = 4" in w for w in r.interpretation.warnings)
