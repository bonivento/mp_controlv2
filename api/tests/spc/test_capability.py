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
from app.spc.constants import c4, d2, d3
from app.spc.interpretation import fmt


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
    # Los textos usan coma decimal (hallazgo H12): "1,65".
    assert fmt(res.cpk.value, 3) in res.interpretation.summary
    assert fmt(res.cpk.value, 3) == "1,65"
    one_side = analyze_capability(sg, usl=74.05)
    CapabilityResponse.model_validate(asdict(one_side))


def test_invalid_inputs():
    with pytest.raises(ValueError):
        analyze_capability([[1.0, 2.0], [2.0, 3.0]])
    with pytest.raises(ValueError):
        analyze_capability([[1.0, 2.0], [2.0, 3.0]], lsl=5.0, usl=1.0)
    with pytest.raises(ValueError):
        analyze_capability([[2.0, 2.0], [2.0, 2.0]], lsl=1.0, usl=3.0)


# ------------------------------------------------- grados de libertad (H1)


def test_effective_dof_formulas():
    """ν = 1/(2·CV²) del estimador de sigma, calculado a mano con d2, d3 y c4."""
    from app.spc.capability import frozen_sigma_dof, sigma_dof

    sg = np.random.default_rng(1).normal(size=(25, 5)).tolist()
    # R̄/d2: ν = m·d2²/(2·d3²) = 25·2.326²/(2·0.864²) ≈ 90.6 (el validador midió 90.5).
    nu_r = sigma_dof(sg, "rbar_d2")
    assert nu_r == pytest.approx(25 * d2(5) ** 2 / (2 * d3(5) ** 2))
    assert nu_r == pytest.approx(90.6, abs=0.1)
    # S̄/c4: ν = m·c4²/(2(1 - c4²)) ≈ 94.9 ≈ 0.95·m(n - 1) (el validador midió 95).
    nu_s = sigma_dof(sg, "sbar_c4")
    assert nu_s == pytest.approx(25 * c4(5) ** 2 / (2 * (1 - c4(5) ** 2)))
    assert nu_s == pytest.approx(0.95 * 25 * 4, rel=0.01)
    # MR̄/d2 con N = 50: k = 49 rangos; Cov(MR_i, MR_i+1) = ((2√3 - 4)/π + 1/3)σ².
    cov = (2 * math.sqrt(3) - 4) / math.pi + 1 / 3
    k = 49
    var = (k * d3(2) ** 2 + 2 * (k - 1) * cov) / k**2
    nu_mr = sigma_dof([[v] for v in range(50)], "mrbar_d2")
    assert nu_mr == pytest.approx(d2(2) ** 2 / (2 * var))
    assert nu_mr == pytest.approx(0.61 * 49, rel=0.02)
    # Límites congelados: el ν de la Fase I.
    lim = {"chart_type": "xbar_r", "subgroup_size": 5, "sigma_method": "rbar_d2", "points_used": 25,
           "params": {"mu": 0.0, "sigma": 1.0}}
    assert frozen_sigma_dof(lim) == pytest.approx(nu_r)
    assert frozen_sigma_dof({**lim, "sigma_method": None, "chart_type": "xbar_s"}) == pytest.approx(nu_s)
    assert frozen_sigma_dof({"chart_type": "xbar_r", "params": {"sigma": 1.0}}) is None


def test_mr_covariance_by_simulation():
    """Comprobación de la covarianza de rangos móviles vecinos (0.16275σ²)."""
    x = np.random.default_rng(0).normal(size=400_000)
    mr = np.abs(np.diff(x))
    assert np.cov(mr[:-1], mr[1:])[0, 1] == pytest.approx((2 * math.sqrt(3) - 4) / math.pi + 1 / 3, abs=0.004)


def _coverage(make_sigma, dof, reps=3000, seed=11):
    rng = np.random.default_rng(seed)
    hits = 0
    for _ in range(reps):
        s = make_sigma(rng)
        lo, hi = cp_confidence_interval(1.0 / s, 100, 0.95, dof)  # Cp real = 1 con σ = 1
        hits += lo <= 1.0 <= hi
    return hits / reps


def test_cp_interval_coverage_with_effective_dof():
    """Cobertura real del IC 95 % de Cp con el ν efectivo (3000 réplicas, EE ≈ 0.004).

    Con N - 1 grados de libertad el validador midió 0.915 (R̄/d2), 0.868 (MR̄/d2)
    y 0.601 (sigma congelada de una Fase I de 25 × 5 con 500 datos nuevos).
    """
    from app.spc.capability import sigma_dof

    rbar = lambda r: np.ptp(r.standard_normal((25, 5)), axis=1).mean() / d2(5)
    nu = sigma_dof([[0.0] * 5] * 25, "rbar_d2")
    assert 0.935 <= _coverage(rbar, nu) <= 0.965
    mrbar = lambda r: np.abs(np.diff(r.standard_normal(50))).mean() / d2(2)
    nu = sigma_dof([[0.0]] * 50, "mrbar_d2")
    assert 0.935 <= _coverage(mrbar, nu) <= 0.965


def test_frozen_limits_use_phase_one_dof_and_n_for_the_mean():
    rng = np.random.default_rng(3)
    lim = {"chart_type": "xbar_r", "subgroup_size": 5, "sigma_method": "rbar_d2", "points_used": 25,
           "params": {"mu": 0.0, "sigma": 1.0}}
    sg = rng.normal(0, 1, (100, 5)).tolist()
    res = analyze_capability(sg, lsl=-4.0, usl=4.0, limits=lim)
    nu = 25 * d2(5) ** 2 / (2 * d3(5) ** 2)
    lo, hi = cp_confidence_interval(8 / 6, 500, 0.95, nu)
    assert (res.cp.lower, res.cp.upper) == pytest.approx((lo, hi))
    # Bissell: 1/(9n) con los 500 datos nuevos (media) y 1/(2ν) con la Fase I (sigma).
    k = res.cpk.value
    z = stats.norm.ppf(0.975)
    se = math.sqrt(1 / (9 * 500) + k**2 / (2 * nu))
    assert (res.cpk.lower, res.cpk.upper) == pytest.approx((k - z * se, k + z * se))
    assert any("ν ≈ 90,6" in w and "Fase I" in w for w in res.interpretation.warnings)
    # Sin la información de Fase I no hay intervalos (y se explica).
    res2 = analyze_capability(sg, lsl=-4.0, usl=4.0, limits={"chart_type": "xbar_r", "params": {"sigma": 1.0}})
    assert res2.cp.lower is None and res2.cpk.lower is None and res2.ppk.lower is not None
    assert any("no se calcularon" in w for w in res2.interpretation.warnings)
    CapabilityResponse.model_validate(asdict(res2))


def test_variable_subgroup_size_uses_pooled_sd():
    """n variable con S: s_p = √(Σ(n_i - 1)S_i²/Σ(n_i - 1)) / c4(ν + 1) (Montgomery 6.3.2)."""
    rng = np.random.default_rng(4)
    sg = [rng.normal(0, 1, k).tolist() for k in (2, 15, 3, 10, 5, 8)]
    nu = sum(len(g) - 1 for g in sg)
    sp = math.sqrt(sum((len(g) - 1) * np.var(g, ddof=1) for g in sg) / nu)
    sigma, method = short_term_sigma(sg)
    assert method == "sbar_c4" and sigma == pytest.approx(sp / c4(nu + 1))
    from app.spc.capability import sigma_dof

    assert sigma_dof(sg, "sbar_c4") == nu


# ------------------------------------------------------- robustez (H2, H14)


def test_non_finite_specs_are_rejected():
    sg = [[1, 2], [2, 3.5], [1.5, 2.5]]
    for kw in ({"lsl": float("nan"), "usl": 5.0}, {"usl": float("inf")}, {"lsl": 0.0, "usl": 5.0, "target": float("nan")}):
        with pytest.raises(ValueError):
            analyze_capability(sg, **kw)
    with pytest.raises(ValueError):
        capability_verdict(float("nan"))


def test_target_outside_specs_leaves_cpm_null_with_warning():
    sg = np.random.default_rng(5).normal(10, 0.2, (25, 5)).tolist()
    res = analyze_capability(sg, lsl=9.4, usl=10.7, target=11.5)
    assert res.cpm.value is None
    assert any("fuera de las especificaciones" in w and "Cpm" in w for w in res.interpretation.warnings)


# ---------------------------------------------------------- textos (H7, H9, S4)


def test_summary_without_confirmed_stability_is_conditional():
    sg = np.random.default_rng(2).normal(10, 0.2, (25, 5)).tolist()
    s_none = analyze_capability(sg, lsl=9.0, usl=11.0).interpretation.summary
    assert s_none.startswith("No se confirmó que el proceso esté en control") and "condicional" in s_none
    s_false = analyze_capability(sg, lsl=9.0, usl=11.0, is_stable=False).interpretation.summary
    assert s_false.startswith("El proceso no está en control estadístico") and "no se puede declarar" in s_false
    s_true = analyze_capability(sg, lsl=9.0, usl=11.0, is_stable=True, is_normal=True).interpretation.summary
    assert s_true.startswith("Con especificaciones") and "veredicto de capacidad adecuado" in s_true


def test_one_sided_bound_is_used_for_one_sided_claims():
    """S4: "con 95 % de confianza Cpk supera…" usa Ĉ - z_0.95·EE, no el extremo bilateral."""
    sg = np.random.default_rng(2).normal(10, 0.2, (25, 5)).tolist()
    res = analyze_capability(sg, lsl=9.0, usl=11.0, is_stable=True, is_normal=True)
    k, lo = res.cpk.value, res.cpk.lower
    se = (k - lo) / stats.norm.ppf(0.975)
    lb1 = k - stats.norm.ppf(0.95) * se
    text = " ".join(res.interpretation.findings)
    assert f"cota inferior de confianza unilateral del 95 % para Cpk es {fmt(lb1, 3)}" in text
    assert "es al menos" not in text


def test_sigma_ratio_is_compared_with_chance():
    """H9: con I-MR estable, N = 30, una razón de 1.15 está dentro del azar."""
    for seed in range(400):
        x = np.random.default_rng(seed).normal(0, 1, 30)
        r = analyze_capability([[v] for v in x], lsl=-4.0, usl=4.0, is_stable=True, is_normal=True)
        if 1.10 < r.sigma_overall / r.sigma_within < 1.15:
            break
    text = " ".join(r.interpretation.findings)
    assert "compatible con el azar" in text and "Hay variación entre subgrupos" not in text
    # Con un desplazamiento claro entre subgrupos sí se señala (como indicio).
    rng = np.random.default_rng(1)
    sg = (rng.normal(0, 1, (25, 5)) + rng.normal(0, 1.5, (25, 1))).tolist()
    text = " ".join(analyze_capability(sg, lsl=-9.0, usl=9.0, is_stable=True).interpretation.findings)
    assert "mayor que la esperable por azar" in text and "indicio de variación entre subgrupos" in text


# ---------------------------------------------------- tercera ronda (H20, H26, S7)


def test_frozen_imr_dof_counts_only_moving_ranges_used():
    """H26. 30 individuales (índices 0 a 29) con los puntos 5, 15 y 25 excluidos. Cada
    exclusión intermedia quita dos rangos móviles, así que quedan 29 - 6 = 23. Contados
    a mano por el índice del segundo punto, los tramos retenidos son 1-4, 7-14, 17-24 y
    27-29 (4, 8, 8 y 3 rangos), con 3 + 7 + 7 + 2 = 19 pares de rangos vecinos.
    ν = d2²·k²/(2(k·d3² + 2v·0.16275)) con k = 23 y v = 19."""
    from app.spc import phases
    from app.spc.capability import frozen_sigma_dof
    x = np.random.default_rng(0).standard_normal(30).tolist()
    lim = phases.phase_one("i_mr", x, excluded=[(i, "causa") for i in (5, 15, 25)]).limits.to_contract()
    k, v = 23, 19
    cov = (2 * math.sqrt(3) - 4) / math.pi + 1 / 3
    expected = d2(2) ** 2 * k * k / (2 * (k * d3(2) ** 2 + 2 * v * cov))
    assert frozen_sigma_dof(lim) == pytest.approx(expected, rel=1e-12)
    # Sin exclusiones se mantiene la serie consecutiva de N - 1 rangos.
    lim0 = phases.phase_one("i_mr", x).limits.to_contract()
    k0 = 29
    assert frozen_sigma_dof(lim0) == pytest.approx(
        d2(2) ** 2 * k0 * k0 / (2 * (k0 * d3(2) ** 2 + 2 * (k0 - 1) * cov)), rel=1e-12)


def test_mr_dof_limit_is_0_6050_k():
    """El límite de ν/k cuando k crece es d2²/(2(d3² + 2·0.16275)) = 0.6050."""
    from app.spc.capability import _dof_mrbar
    assert _dof_mrbar(10**7) / 10**7 == pytest.approx(0.6050, abs=1e-4)


@pytest.mark.parametrize("stable", [False, None])
def test_one_sided_bound_is_conditional_without_stability(stable):
    """H20: sin estabilidad confirmada la cota no se afirma con confianza."""
    sg = np.random.default_rng(2).normal(10, 0.2, (25, 5)).tolist()
    it = analyze_capability(sg, lsl=8.5, usl=11.5, is_stable=stable, is_normal=True).interpretation
    text = " ".join(it.findings)
    assert "de confianza Cpk supera" not in text
    assert "sería" in text and "si el proceso fuera estable" in text
    firm = analyze_capability(sg, lsl=8.5, usl=11.5, is_stable=True, is_normal=True).interpretation
    assert any("de confianza Cpk supera" in f for f in firm.findings)


def test_summary_flags_point_verdict_when_bound_misses_minimum():
    """S7: Cpk puntual >= 1.33 pero cota unilateral < 1.33: el resumen no da el veredicto como firme."""
    sg = np.random.default_rng(2).normal(10, 0.2, (25, 5)).tolist()
    # Se elige el ancho de especificación para que Cpk quede justo por encima de 1.33.
    for half in np.arange(0.80, 0.95, 0.005):
        res = analyze_capability(sg, lsl=10 - half, usl=10 + half, is_stable=True, is_normal=True)
        k, lo = res.cpk.value, res.cpk.lower
        lb1 = k - stats.norm.ppf(0.95) * (k - lo) / stats.norm.ppf(0.975)
        if k >= 1.33 > lb1:
            break
    else:
        pytest.fail("no se encontró el caso")
    s = res.interpretation.summary
    assert "según la estimación puntual" in s and "no es concluyente" in s and fmt(lb1, 3) in s
    assert " de el " not in s
