"""Pruebas de constants.py contra el apéndice VI de Montgomery.

Tabla transcrita de Montgomery, *Introduction to Statistical Quality Control*,
apéndice VI "Factors for Constructing Variables Control Charts" (n = 2..25).
Columnas: A, A2, A3, c4, B3, B4, B5, B6, d2, d3, D1, D2, D3, D4.

La tabla del libro está redondeada a 3 decimales (c4 a 4). Los factores se
derivan aquí de d2 y d3 con 6 decimales y de c4 exacto, así que la diferencia
esperada es solo de redondeo (≤ 0.0005 más el redondeo de las entradas). D1 y D2
del libro se calcularon con d2 y d3 ya redondeados a 3 decimales; por eso su
tolerancia es 0.002 (3·0.0005 + 0.0005).
"""

import math

import numpy as np
import pytest
from scipy import integrate, stats

from app.spc import constants as K
from app.spc.constants import SPCInputError

APPENDIX_VI = """
2 2.121 1.880 2.659 0.7979 0 3.267 0 2.606 1.128 0.853 0 3.686 0 3.267
3 1.732 1.023 1.954 0.8862 0 2.568 0 2.276 1.693 0.888 0 4.358 0 2.574
4 1.500 0.729 1.628 0.9213 0 2.266 0 2.088 2.059 0.880 0 4.698 0 2.282
5 1.342 0.577 1.427 0.9400 0 2.089 0 1.964 2.326 0.864 0 4.918 0 2.114
6 1.225 0.483 1.287 0.9515 0.030 1.970 0.029 1.874 2.534 0.848 0 5.078 0 2.004
7 1.134 0.419 1.182 0.9594 0.118 1.882 0.113 1.806 2.704 0.833 0.204 5.204 0.076 1.924
8 1.061 0.373 1.099 0.9650 0.185 1.815 0.179 1.751 2.847 0.820 0.388 5.306 0.136 1.864
9 1.000 0.337 1.032 0.9693 0.239 1.761 0.232 1.707 2.970 0.808 0.547 5.393 0.184 1.816
10 0.949 0.308 0.975 0.9727 0.284 1.716 0.276 1.669 3.078 0.797 0.687 5.469 0.223 1.777
11 0.905 0.285 0.927 0.9754 0.321 1.679 0.313 1.637 3.173 0.787 0.811 5.535 0.256 1.744
12 0.866 0.266 0.886 0.9776 0.354 1.646 0.346 1.610 3.258 0.778 0.922 5.594 0.283 1.717
13 0.832 0.249 0.850 0.9794 0.382 1.618 0.374 1.585 3.336 0.770 1.025 5.647 0.307 1.693
14 0.802 0.235 0.817 0.9810 0.406 1.594 0.399 1.563 3.407 0.763 1.118 5.696 0.328 1.672
15 0.775 0.223 0.789 0.9823 0.428 1.572 0.421 1.544 3.472 0.756 1.203 5.741 0.347 1.653
16 0.750 0.212 0.763 0.9835 0.448 1.552 0.440 1.526 3.532 0.750 1.282 5.782 0.363 1.637
17 0.728 0.203 0.739 0.9845 0.466 1.534 0.458 1.511 3.588 0.744 1.356 5.820 0.378 1.622
18 0.707 0.194 0.718 0.9854 0.482 1.518 0.475 1.496 3.640 0.739 1.424 5.856 0.391 1.608
19 0.688 0.187 0.698 0.9862 0.497 1.503 0.490 1.483 3.689 0.734 1.487 5.891 0.403 1.597
20 0.671 0.180 0.680 0.9869 0.510 1.490 0.504 1.470 3.735 0.729 1.549 5.921 0.415 1.585
21 0.655 0.173 0.663 0.9876 0.523 1.477 0.516 1.459 3.778 0.724 1.605 5.951 0.425 1.575
22 0.640 0.167 0.647 0.9882 0.534 1.466 0.528 1.448 3.819 0.720 1.659 5.979 0.434 1.566
23 0.626 0.162 0.633 0.9887 0.545 1.455 0.539 1.438 3.858 0.716 1.710 6.006 0.443 1.557
24 0.612 0.157 0.619 0.9892 0.555 1.445 0.549 1.429 3.895 0.712 1.759 6.031 0.451 1.548
25 0.600 0.153 0.606 0.9896 0.565 1.435 0.559 1.420 3.931 0.708 1.806 6.056 0.459 1.541
"""
COLUMNS = ["A", "A2", "A3", "c4", "B3", "B4", "B5", "B6", "d2", "d3", "D1", "D2", "D3", "D4"]
TABLE = {
    int(line.split()[0]): dict(zip(COLUMNS, map(float, line.split()[1:])))
    for line in APPENDIX_VI.strip().splitlines()
}
TOL = {k: 0.0008 for k in COLUMNS} | {"c4": 0.00006, "D1": 0.002, "D2": 0.002}


@pytest.mark.parametrize("n", sorted(TABLE))
@pytest.mark.parametrize("name", COLUMNS)
def test_factor_matches_appendix_vi(n, name):
    computed = getattr(K, name)(n)
    assert computed == pytest.approx(TABLE[n][name], abs=TOL[name])


@pytest.mark.parametrize("n", sorted(TABLE))
def test_d2_d3_round_to_appendix(n):
    assert round(K.d2(n), 3) == TABLE[n]["d2"]
    if n == 19:
        # El apéndice imprime 0.734; la integración da 0.733481, que redondea a
        # 0.733. La diferencia (0.00052) es de redondeo de la tabla original.
        assert K.d3(n) == pytest.approx(TABLE[n]["d3"], abs=0.00055)
    else:
        assert round(K.d3(n), 3) == TABLE[n]["d3"]


@pytest.mark.parametrize("n", [2, 3, 5, 10, 25])
def test_d2_d3_equal_numerical_integration(n):
    """d2 = ∫[1 - Φ^n - (1-Φ)^n]; E[W²] por integral doble (Montgomery 6.2.1)."""
    phi = stats.norm.cdf
    d2 = integrate.quad(lambda x: 1 - phi(x) ** n - (1 - phi(x)) ** n, -np.inf, np.inf)[0]
    f = lambda x, y: 1 - phi(y) ** n - (1 - phi(x)) ** n + (phi(y) - phi(x)) ** n
    ew2 = 2 * integrate.dblquad(f, -10, 10, lambda y: -10, lambda y: y, epsabs=1e-10)[0]
    assert K.d2(n) == pytest.approx(d2, abs=2e-6)
    assert K.d3(n) == pytest.approx(math.sqrt(ew2 - d2**2), abs=2e-6)


def test_d2_by_simulation_sanity():
    """Control independiente: E[R] de normales estándar con n = 5 ≈ 2.326."""
    rng = np.random.default_rng(12345)
    x = rng.standard_normal((200_000, 5))
    r = x.max(axis=1) - x.min(axis=1)
    assert r.mean() == pytest.approx(K.d2(5), abs=0.01)
    assert r.std(ddof=1) == pytest.approx(K.d3(5), abs=0.01)


def test_c4_exact_values():
    # c4(2) = sqrt(2/pi) exacto; c4(3) = sqrt(pi)/2 exacto.
    assert K.c4(2) == pytest.approx(math.sqrt(2 / math.pi), rel=1e-12)
    assert K.c4(3) == pytest.approx(math.sqrt(math.pi) / 2, rel=1e-12)
    # c4 ≈ 4(n-1)/(4n-3) para n grande (Montgomery, nota del apéndice VI).
    assert K.c4(100) == pytest.approx(4 * 99 / 397, abs=1e-5)
    assert K.c4(1000) < 1.0


def test_factors_with_other_width():
    # Con L = 2: A2 = 2/(d2·sqrt n), D4 = 1 + 2·d3/d2.
    assert K.A2(5, L=2) == pytest.approx(2 / (K.d2(5) * math.sqrt(5)))
    assert K.D4(5, L=2) == pytest.approx(1 + 2 * K.d3(5) / K.d2(5))
    assert K.D3(7, L=2) == pytest.approx(1 - 2 * K.d3(7) / K.d2(7))


def test_consistency_between_factor_families():
    for n in range(2, 26):
        assert K.D4(n) * K.d2(n) == pytest.approx(K.D2(n))
        assert K.B6(n) == pytest.approx(K.B4(n) * K.c4(n))
        assert K.A2(n) * K.d2(n) == pytest.approx(K.A(n))


@pytest.mark.parametrize("bad", [1, 0, -3, 2.5, True])
def test_invalid_n(bad):
    with pytest.raises(SPCInputError):
        K.c4(bad)


def test_range_constants_out_of_table():
    with pytest.raises(SPCInputError):
        K.d2(26)
    with pytest.raises(SPCInputError):
        K.D4(30)
    # c4 y los factores B sí existen para n > 25
    assert 0 < K.B3(30) < 1 < K.B4(30)
    assert "d2" not in K.factor_table(30)
    assert K.factor_table(5)["A2"] == pytest.approx(0.577, abs=5e-4)
