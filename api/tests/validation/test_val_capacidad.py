"""Validación independiente de capability.py.

- Índices y fracción no conforme recalculados a mano.
- Cobertura real de los intervalos de confianza por simulación (duda 11).
- Robustez: especificaciones no finitas, objetivo fuera de especificación.
"""

import math

import numpy as np
import pytest
from scipy import stats

from app.spc import constants as K
from app.spc.capability import (
    analyze_capability,
    bissell_interval,
    cp_confidence_interval,
    frozen_sigma_dof,
    sigma_dof,
)

from .independiente import d2_por_maximo, d3_por_momentos


def _datos(seed=5, m=25, n=5, mu=10.0, sd=0.2):
    return np.random.default_rng(seed).normal(mu, sd, (m, n)).tolist()


def test_indices_a_mano_con_rbar_d2():
    sg = _datos()
    x = np.array(sg)
    mean = x.mean()
    sw = np.mean([max(g) - min(g) for g in sg]) / K.d2(5)
    so = x.std(ddof=1)
    lsl, usl, T = 9.4, 10.7, 10.1
    r = analyze_capability(sg, lsl=lsl, usl=usl, target=T)
    assert r.sigma_within == pytest.approx(sw, rel=1e-6)
    assert r.cp.value == pytest.approx((usl - lsl) / (6 * sw), rel=1e-6)
    assert r.cpl.value == pytest.approx((mean - lsl) / (3 * sw), rel=1e-6)
    assert r.cpu.value == pytest.approx((usl - mean) / (3 * sw), rel=1e-6)
    assert r.cpk.value == pytest.approx(min(r.cpl.value, r.cpu.value))
    assert r.ppk.value == pytest.approx(min(usl - mean, mean - lsl) / (3 * so), rel=1e-12)
    tau = math.sqrt(so**2 + (mean - T) ** 2)
    assert r.cpm.value == pytest.approx(min(T - lsl, usl - T) / (3 * tau), rel=1e-12)
    # fracción no conforme por cola con la normal (sigma de corto y de largo plazo)
    assert r.expected_within.below_lsl == pytest.approx(stats.norm.cdf((lsl - mean) / sw), rel=1e-6)
    assert r.expected_within.above_usl == pytest.approx(stats.norm.sf((usl - mean) / sw), rel=1e-6)
    assert r.expected_overall.total == pytest.approx(
        stats.norm.cdf((lsl - mean) / so) + stats.norm.sf((usl - mean) / so), rel=1e-9)
    assert r.observed.total == pytest.approx(np.mean((x < lsl) | (x > usl)))


def test_intervalos_a_mano():
    lo, hi = cp_confidence_interval(1.5, 40, 0.90)
    assert lo == pytest.approx(1.5 * math.sqrt(stats.chi2.ppf(0.05, 39) / 39))
    assert hi == pytest.approx(1.5 * math.sqrt(stats.chi2.isf(0.05, 39) / 39))
    lo, hi = bissell_interval(1.2, 60, 0.95)
    se = math.sqrt(1 / (9 * 60) + 1.2**2 / (2 * 59))
    assert (lo, hi) == pytest.approx((1.2 - 1.959964 * se, 1.2 + 1.959964 * se), abs=1e-6)
    lo, hi = bissell_interval(-0.4, 60, 0.95)          # índice negativo: mismo semiancho
    se = math.sqrt(1 / (9 * 60) + 0.16 / (2 * 59))
    assert (lo, hi) == pytest.approx((-0.4 - 1.959964 * se, -0.4 + 1.959964 * se), abs=1e-6)


def test_una_sola_especificacion():
    sg = _datos()
    r = analyze_capability(sg, usl=10.7)
    assert r.cp.value is None and r.cpl.value is None and r.pp.value is None
    assert r.cpk.value == pytest.approx(r.cpu.value)
    assert r.expected_within.below_lsl is None
    assert r.expected_within.total == pytest.approx(r.expected_within.above_usl)


def _cobertura_cp(gen, N, reps=6000, seed=42, dof=None):
    """Cobertura del IC 95 % de Cp con σ̂ = gen(rng) y los grados de libertad `dof`
    (None: los N - 1 del libro, que solo valen para la desviación muestral)."""
    rng = np.random.default_rng(seed)
    cp_true = 8 / 6
    hits = 0
    for _ in range(reps):
        s = gen(rng)
        lo, hi = cp_confidence_interval(8 / (6 * s), N, dof=dof)
        hits += lo <= cp_true <= hi
    return hits / reps


def _rbar_d2(r):
    return np.ptp(r.standard_normal((25, 5)), axis=1).mean() / d2_por_maximo(5)


def _nu_rbar_propio(m, n):
    """ν = m·d2²/(2·d3²) con d2 y d3 de otras integrales (independiente.py)."""
    return m * d2_por_maximo(n) ** 2 / (2 * d3_por_momentos(n) ** 2)


def test_cobertura_con_desviacion_muestral_es_nominal():
    c = _cobertura_cp(lambda r: r.standard_normal(125).std(ddof=1), 125)
    assert 0.94 <= c <= 0.96


def test_cobertura_con_rbar_d2():
    """H1, corregido. Antes esta prueba llamaba a `cp_confidence_interval(cp, N)` sin `dof`
    (ν = N - 1, la fórmula del libro) y no podía pasar con ningún código: medía la
    fórmula con un ν equivocado, no el camino del software. Ahora mide el intervalo que
    usa `analyze_capability`: el mismo de `cp_confidence_interval` con ν = `sigma_dof`.
    Con ν = N - 1 = 124 la cobertura era 0.905; con ν efectivo ≈ 90.6, 0.947
    (5 000 réplicas de `analyze_capability` en docs/validacion.md)."""
    sg = np.random.default_rng(0).standard_normal((25, 5)).tolist()
    nu = sigma_dof(sg, "rbar_d2")
    assert nu == pytest.approx(_nu_rbar_propio(25, 5), rel=1e-5)
    r = analyze_capability(sg, lsl=-4.0, usl=4.0)
    assert r.sigma_method == "rbar_d2"
    assert (r.cp.lower, r.cp.upper) == pytest.approx(cp_confidence_interval(r.cp.value, 125, dof=nu), rel=1e-12)
    c = _cobertura_cp(_rbar_d2, 125, dof=nu)
    assert 0.935 <= c <= 0.965


def test_cobertura_con_limites_congelados():
    """H1, corregido. σ congelada de una Fase I de 25 × 5 con N = 500 datos nuevos: el IC
    debe usar el ν de la Fase I (≈ 90.6), no N - 1 = 499 (cobertura 0.59 con ν = N - 1)."""
    lim = {"chart_type": "xbar_r", "subgroup_size": 5, "sigma_method": "rbar_d2", "points_used": 25,
           "params": {"mu": 0.0, "sigma": 1.0}}
    nu = frozen_sigma_dof(lim)
    assert nu == pytest.approx(_nu_rbar_propio(25, 5), rel=1e-5)
    nuevos = np.random.default_rng(1).standard_normal((100, 5)).tolist()
    r = analyze_capability(nuevos, lsl=-4.0, usl=4.0, limits=lim)
    assert r.sigma_method == "frozen_limits"
    assert (r.cp.lower, r.cp.upper) == pytest.approx(cp_confidence_interval(r.cp.value, 500, dof=nu), rel=1e-12)
    c = _cobertura_cp(_rbar_d2, 500, dof=nu)
    assert 0.935 <= c <= 0.965


def test_cobertura_bissell_con_mrbar_d2():
    """H1, corregido. Cpk con MR̄/d2 y N = 50 (Cpk real 4/3, proceso descentrado):
    con ν = N - 1 la cobertura era 0.879; con el ν efectivo (≈ 29.8) es nominal.
    ν propio por simulación del CV de MR̄: 29.77; el del software, 29.83."""
    nu = sigma_dof([[0.0]] * 50, "mrbar_d2")
    rng = np.random.default_rng(3)
    v = np.array([np.abs(np.diff(rng.standard_normal(50))).mean() for _ in range(40_000)])
    assert nu == pytest.approx(1 / (2 * (v.std(ddof=1) / v.mean()) ** 2), rel=0.03)
    hits, reps = 0, 6000
    for _ in range(reps):
        x = rng.standard_normal(50)
        s = np.abs(np.diff(x)).mean() / d2_por_maximo(2)
        cpk = min(4.0 - x.mean(), x.mean() + 5.0) / (3 * s)
        lo, hi = bissell_interval(cpk, 50, dof=nu)
        hits += lo <= 4 / 3 <= hi
    assert 0.935 <= hits / reps <= 0.965


def test_cota_unilateral_de_cpk_a_mano():
    """S4, corregido: la frase "con 95 % de confianza Cpk supera …" usa Ĉ - z_0.95·EE
    (cobertura medida 0.953 con R̄/d2 25 × 5 y 0.955 con MR̄/d2, N = 50)."""
    sg = np.random.default_rng(2).normal(10, 0.2, (25, 5)).tolist()
    r = analyze_capability(sg, lsl=8.5, usl=11.5, is_stable=True, is_normal=True)
    nu = sigma_dof(sg, "rbar_d2")
    se = math.sqrt(1 / (9 * 125) + r.cpk.value ** 2 / (2 * nu))
    lb = r.cpk.value - stats.norm.ppf(0.95) * se
    texto = " ".join(r.interpretation.findings)
    assert f"unilateral del 95 % para Cpk es {lb:.3g}".replace(".", ",") in texto


def test_especificacion_nan_se_rechaza():
    with pytest.raises(ValueError):
        analyze_capability(_datos(), lsl=float("nan"), usl=10.7)


def test_objetivo_fuera_de_especificacion():
    r = analyze_capability(_datos(), lsl=9.4, usl=10.7, target=11.5)
    assert r.cpm.value is None or r.cpm.value >= 0


def _nu_mr_exacto(m_total, excluidos):
    """ν de MR̄/d2 contando solo los MR con ambos puntos retenidos y las covarianzas
    entre MR vecinos que efectivamente existen (Cov = 0.16275σ², ver fundamentos)."""
    keep = [i not in excluidos for i in range(m_total)]
    pares = [keep[i] and keep[i - 1] for i in range(1, m_total)]
    k = sum(pares)
    vecinos = sum(1 for i in range(1, len(pares)) if pares[i] and pares[i - 1])
    d2sq, d3sq = d2_por_maximo(2) ** 2, d3_por_momentos(2) ** 2
    cov = (2 * math.sqrt(3) - 4) / math.pi + 1 / 3
    return d2sq * k * k / (2 * (k * d3sq + 2 * vecinos * cov))


def test_nu_congelado_i_mr_con_exclusiones():
    from app.spc import phases
    x = np.random.default_rng(0).standard_normal(30).tolist()
    excl = [5, 15, 25]
    lim = phases.phase_one("i_mr", x, excluded=[(i, "causa") for i in excl]).limits.to_contract()
    assert frozen_sigma_dof(lim) == pytest.approx(_nu_mr_exacto(30, set(excl)), rel=0.01)
