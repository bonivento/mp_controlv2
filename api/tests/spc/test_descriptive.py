"""Pruebas de estadística descriptiva, resumen por subgrupo y atípicos."""

import math
from dataclasses import asdict

import numpy as np
import pytest

from app.schemas.data import SummaryResponse
from app.spc.descriptive import (
    build_histogram,
    describe,
    flag_outliers_iqr,
    sturges_bins,
    summarize,
    summarize_subgroups,
    tukey_fences,
)


def test_describe_one_to_ten_hand_calculated():
    # Esperados calculados a mano para x = 1..10:
    # media 5.5; s² = Σ(x - 5.5)²/9 = 82.5/9; cuartiles tipo 7: 3.25, 5.5, 7.75.
    # Distribución simétrica: asimetría 0. Exceso de curtosis G2 (ajustado):
    # G2 = [(n+1)·g2 + 6]·(n-1)/((n-2)(n-3)), g2 = m4/m2² - 3, m2 = 8.25, m4 = 120.8625.
    d = describe(list(range(1, 11)))
    assert d.count == 10
    assert d.mean == pytest.approx(5.5)
    assert d.std == pytest.approx(math.sqrt(82.5 / 9))
    assert (d.q1, d.median, d.q3) == pytest.approx((3.25, 5.5, 7.75))
    assert d.skewness == pytest.approx(0.0, abs=1e-12)
    m2, m4 = 8.25, 120.8625
    g2 = m4 / m2**2 - 3
    G2 = ((11 * g2 + 6) * 9) / (8 * 7)
    assert d.kurtosis == pytest.approx(G2)
    assert d.kurtosis == pytest.approx(-1.2)


def test_describe_small_samples_and_zero_variance():
    one = describe([4.0])
    assert one.std == 0.0 and one.skewness is None and one.kurtosis is None
    flat = describe([2.0, 2.0, 2.0, 2.0, 2.0])
    assert flat.std == 0.0 and flat.skewness is None and flat.kurtosis is None
    three = describe([1.0, 2.0, 4.0])
    assert three.skewness is not None and three.kurtosis is None


def test_rejects_nan_and_empty():
    with pytest.raises(ValueError):
        describe([1.0, float("nan")])
    with pytest.raises(ValueError):
        describe([])
    with pytest.raises(ValueError):
        summarize([[1.0, 2.0], []])


def test_subgroup_summary_ranges_and_individuals():
    s = summarize_subgroups([[1.0, 4.0, 2.0], [5.0]], labels=["A", "B"])
    assert s[0].label == "A" and s[0].n == 3
    assert s[0].mean == pytest.approx(7 / 3)
    assert s[0].range == pytest.approx(3.0)
    assert s[0].std == pytest.approx(np.std([1, 4, 2], ddof=1))
    assert s[1].range is None and s[1].std is None


def test_tukey_outliers_marked_not_removed():
    groups = [[10.0, 11.0, 12.0], [11.0, 10.0, 30.0]]
    # Cuartiles tipo 7 de {10, 10, 11, 11, 12, 30}: Q1 = 10.25, Q3 = 11.75, IQR = 1.5.
    low, high = tukey_fences([10, 11, 12, 11, 10, 30])
    assert (low, high) == pytest.approx((10.25 - 2.25, 11.75 + 2.25))
    flags = flag_outliers_iqr(groups)
    assert len(flags) == 1
    f = flags[0]
    assert (f.subgroup_index, f.position, f.value) == (1, 2, 30.0)
    assert "Tukey" in f.reason and "30" in f.reason and "causa asignable" in f.reason
    res = summarize(groups)
    assert res.overall.count == 6  # el atípico sigue en los datos
    assert res.constant_size is True


def test_summary_converts_to_contract():
    res = summarize([[1.0, 2.0, 3.0], [2.0, 2.5], [9.0]], labels=["L1", "L2", "L3"])
    model = SummaryResponse.model_validate(asdict(res))
    assert model.constant_size is False
    assert model.subgroups[2].range is None


def test_histogram_sturges_and_curve_scale():
    rng = np.random.default_rng(7)
    x = rng.normal(50, 4, 200)
    h = build_histogram(x)
    k = sturges_bins(200)
    assert k == 9  # ceil(log2 200) + 1 = 8 + 1
    assert len(h.edges) == k + 1 and len(h.counts) == k
    assert sum(h.counts) == 200
    # Escala de frecuencia: el área bajo la curva es N·w·(fracción de la normal en el rango).
    w = h.edges[1] - h.edges[0]
    xs, ys = np.array(h.normal_curve_x), np.array(h.normal_curve_y)
    area = np.trapezoid(ys, xs)
    assert area == pytest.approx(200 * w, rel=0.01)


def test_histogram_extends_to_specs_and_handles_constant():
    h = build_histogram([1.0, 2.0, 3.0, 4.0], extend_to=(-10.0, None, 20.0))
    assert h.normal_curve_x[0] == pytest.approx(-10.0)
    assert h.normal_curve_x[-1] == pytest.approx(20.0)
    flat = build_histogram([5.0, 5.0, 5.0])
    assert flat.normal_curve_x == [] and sum(flat.counts) == 3
