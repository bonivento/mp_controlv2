"""Pruebas de capacidad del proceso.

Casos de libro (Montgomery, *Introduction to Statistical Quality Control*):
- Cap. 6, anillos de pistón (diámetro interior, 25 subgrupos de n = 5,
  x̿ = 74.001, R̄ = 0.023, especificaciones 74 ± 0.05): σ̂ = R̄/d2 = 0.0099 y
  Cp = 1.68. Sin la tabla original, se construyen subgrupos con exactamente
  esos estadísticos resumen.
- Cap. 8, resistencia al estallido de envases de vidrio (x̄ = 264.06,
  s = 32.02, LSL = 200 psi): Cpl = 0.67. Se construyen 100 datos con esa
  media y esa desviación.
- Cap. 8, intervalo chi-cuadrado para Cp (Ejemplo 8.5 de la 6.ª ed.):
  n = 20, Ĉp = 2.29 -> 1.57 <= Cp <= 3.01.
- Cap. 8, intervalo de Bissell para Cpk (Ejemplo 8.6 de la 6.ª ed.):
  n = 20, Ĉpk = 1.33 -> 0.88 <= Cpk <= 1.78.
"""

import math
from dataclasses import asdict

import numpy as np
import pytest
from scipy import stats

from app.schemas.capability import CapabilityResponse
from app.spc.capability import (
    analyze_capability,
    bissell_interval,
    capability_verdict,
    cp_confidence_interval,
    short_term_sigma,
    sigma_mrbar_d2,
)
from app.spc.constants import d2


def _piston_ring_like():
    """25 subgrupos de 5 con R_i = 0.023 y gran media 74.001 exactas."""
    offsets = np.array([-0.0115, -0.005, 0.0, 0.005, 0.0115])
    centers = 74.001 + 0.002 * np.sin(np.arange(25))
    centers += 74.001 - centers.mean()
    return [list(c + offsets) for c in centers]


def test_piston_ring_cp_montgomery_ch6():
    sg = _piston_ring_like()
    res = analyze_capability(sg, lsl=73.95, usl=74.05)
    assert res.sigma_method == "rbar_d2"
    assert res.mean == pytest.approx(74.001, abs=1e-9)
    assert res.sigma_within == pytest.approx(0.023 / d2(5))
    assert res.sigma_within == pytest.approx(0.0099, abs=5e-5)
    assert res.cp.value == pytest.approx(1.68, abs=0.01)
    # Cpk = min(USL - x̿, x̿ - LSL)/(3σ) = 0.049/(3·0.023/2.326) calculado a mano.
    assert res.cpk.value == pytest.approx(0.049 / (3 * 0.023 / d2(5)))
    assert res.cpk.value == pytest.approx(res.cpu.value)


def test_bottle_bursting_strength_cpl_montgomery_ch8():
    z = np.random.default_rng(8).normal(size=100)
    x = 264.06 + 32.02 * (z - z.mean()) / z.std(ddof=1)
    res = analyze_capability([[v] for v in x], lsl=200.0)
    assert res.sigma_overall == pytest.approx(32.02)
    assert res.ppl.value == pytest.approx(0.67, abs=0.005)
    assert res.ppk.value == res.ppl.value
    # Una sola especificación: lo que no aplica va en null.
    assert res.cp.value is None and res.pp.value is None
    assert res.cpu.value is None and res.ppu.value is None
    assert res.expected_within.above_usl is None
    assert res.sigma_method == "mrbar_d2"


def test_cp_chi_square_interval_montgomery_example():
    lo, hi = cp_confidence_interval(2.29, 20, 0.95)
    assert lo == pytest.approx(1.57, abs=0.005)
    assert hi == pytest.approx(3.01, abs=0.005)
    # Mismos cuantiles que usa el libro: χ²_{0.025,19} = 8.91 y χ²_{0.975,19} = 32.85.
    assert stats.chi2.ppf(0.025, 19) == pytest.approx(8.91, abs=0.005)
    assert stats.chi2.ppf(0.975, 19) == pytest.approx(32.85, abs=0.005)


def test_cpk_bissell_interval_montgomery_example():
    lo, hi = bissell_interval(1.33, 20, 0.95)
    assert lo == pytest.approx(0.88, abs=0.005)
    assert hi == pytest.approx(1.78, abs=0.005)
    assert bissell_interval(0.0, 20) is None


def test_expected_fraction_with_frozen_sigma():
    rng = np.random.default_rng(3)
    sg = rng.normal(0, 1, (30, 4)).tolist()
    limits = {"chart_type": "xbar_r", "params": {"mu": 0.0, "sigma": 1.0}}
    res = analyze_capability(sg, lsl=-3.0, usl=3.0, limits=limits)
    assert res.sigma_method == "frozen_limits" and res.sigma_within == 1.0
    m = res.mean
    below = stats.norm.cdf(-3 - m)
    above = stats.norm.sf(3 - m)
    assert res.expected_within.below_lsl == pytest.approx(below)
    assert res.expected_within.above_usl == pytest.approx(above)
    assert res.expected_within.total == pytest.approx(below + above)
    assert res.expected_within.ppm == pytest.approx((below + above) * 1e6)
    assert res.cp.value == pytest.approx(1.0)


def test_observed_fraction_counts():
    sg = [[1.0, 2.0], [3.0, 4.0], [5.0, 10.0]]
    res = analyze_capability(sg, lsl=1.5, usl=9.0)
    assert res.observed.below_lsl == pytest.approx(1 / 6)
    assert res.observed.above_usl == pytest.approx(1 / 6)
    assert res.observed.ppm == pytest.approx(2 / 6 * 1e6)


def test_sigma_methods():
    sg = [[1.0, 2.0, 4.0], [2.0, 2.0, 5.0], [3.0, 1.0, 2.0]]
    r_bar = np.mean([3.0, 3.0, 2.0])
    assert short_term_sigma(sg)[0] == pytest.approx(r_bar / d2(3))
    s_vals = [np.std(g, ddof=1) for g in sg]
    from app.spc.constants import c4

    assert short_term_sigma(sg, "sbar_c4")[0] == pytest.approx(np.mean(s_vals) / c4(3))
    # n = 1: MR = 2, 1, 3 -> MR̄ = 2 -> σ = 2/1.128.
    assert sigma_mrbar_d2([1.0, 3.0, 2.0, 5.0]) == pytest.approx(2 / d2(2))
    big = np.random.default_rng(0).normal(size=(5, 12)).tolist()
    assert short_term_sigma(big)[1] == "sbar_c4"
    with pytest.raises(ValueError):
        short_term_sigma([[1.0], [2.0, 3.0]])
    with pytest.raises(ValueError):
        short_term_sigma(sg, "mrbar_d2")


def test_cpm_on_and_off_target():
    z = np.random.default_rng(4).normal(size=60)
    x = 10 + (z - z.mean()) / z.std(ddof=1)  # media 10, s = 1 exactas
    sg = [[v] for v in x]
    on = analyze_capability(sg, lsl=7.0, usl=13.0, target=10.0)
    assert on.cpm.value == pytest.approx(on.pp.value)
    off = analyze_capability(sg, lsl=7.0, usl=13.0, target=11.0)
    # τ = √(1 + 1²) = √2; Cpm = min(11 - 7, 13 - 11)/(3τ) = 2/(3√2), calculado a mano.
    assert off.cpm.value == pytest.approx(2 / (3 * math.sqrt(2)))
    assert analyze_capability(sg, lsl=7.0, usl=13.0).cpm.value is None


def test_verdict_thresholds():
    assert capability_verdict(0.99) == "inadequate"
    assert capability_verdict(1.0) == "marginal"
    assert capability_verdict(1.33) == "adequate"
    assert capability_verdict(1.67) == "excellent"


def test_warns_when_unstable_or_not_normal_but_still_computes():
    sg = _piston_ring_like()
    res = analyze_capability(sg, lsl=73.95, usl=74.05, is_stable=False, is_normal=False)
    assert res.cp.value is not None
    text = " ".join(res.interpretation.warnings)
    assert "no está en control estadístico" in text
    assert "no siguen una distribución normal" in text
    assert "no son confiables" in res.interpretation.summary


def test_converts_to_contract_and_mentions_numbers():
    sg = _piston_ring_like()
    res = analyze_capability(sg, lsl=73.95, usl=74.05, target=74.0, is_stable=True, is_normal=True)
    model = CapabilityResponse.model_validate(asdict(res))
    assert model.verdict == "adequate"  # Cpk = 1.652, entre 1.33 y 1.67
    assert f"{res.cpk.value:.3g}" in res.interpretation.summary
    one_side = analyze_capability(sg, usl=74.05)
    CapabilityResponse.model_validate(asdict(one_side))


def test_invalid_inputs():
    with pytest.raises(ValueError):
        analyze_capability([[1.0, 2.0], [2.0, 3.0]])
    with pytest.raises(ValueError):
        analyze_capability([[1.0, 2.0], [2.0, 3.0]], lsl=5.0, usl=1.0)
    with pytest.raises(ValueError):
        analyze_capability([[2.0, 2.0], [2.0, 2.0]], lsl=1.0, usl=3.0)
