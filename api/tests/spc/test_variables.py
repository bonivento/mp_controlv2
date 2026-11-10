"""Pruebas de variables.py: X-barra-R, X-barra-S e I-MR.

Casos de libro (Montgomery, *Introduction to Statistical Quality Control*):

1. Anillos de pistón, diámetro interior (mm): 25 subgrupos de n = 5.
   Montgomery, cap. 6, sección 6.2.1, tabla 6.3 (6.ª ed.; ejemplo usado también
   en el ejemplo 6.3 para X-barra-S). Resultados publicados:
   x̿ = 74.001, R̄ = 0.023, LCS_X = 74.014, LCI_X = 73.988, LCS_R = 0.049,
   LCI_R = 0; S̄ = 0.0094, LCS_S = 0.0196, LCI_S = 0; sigma ≈ 0.0099 (R̄/d2) y
   ≈ 0.01 (S̄/c4). La tabla del libro trae x̄ y R de cada fila; la prueba
   verifica que los datos transcritos reproducen esas columnas.

2. Costos semanales de procesamiento de hipotecas: 20 observaciones
   individuales. Montgomery, cap. 6, sección 6.4, ejemplo 6.5 (6.ª ed.).
   Publicado: x̄ = 300.5, MR̄ = 7.79, LCS = 321.22, LCI = 279.78,
   LCS_MR = 25.45. El libro usa d2 = 1.128 y D4 = 3.267 redondeados; aquí d2
   tiene 6 decimales, por eso la tolerancia de los límites es 0.01.

El libro calcula los límites con x̿, R̄ y S̄ ya redondeados (74.001, 0.023,
0.0094) y con factores de 3 decimales. Con los promedios sin redondear los
límites cambian en la cuarta cifra decimal (por ejemplo LCS_X del X-barra-S da
74.0146), así que la tolerancia frente al valor publicado es 0.001. Además se
verifica que con los intermedios redondeados del libro se obtiene exactamente
el valor publicado a 3 decimales.
"""

import math

import numpy as np
import pytest

from app.spc import constants as K
from app.spc import variables as V
from app.spc.constants import SPCInputError

PISTON = [
    [74.030, 74.002, 74.019, 73.992, 74.008],
    [73.995, 73.992, 74.001, 74.011, 74.004],
    [73.988, 74.024, 74.021, 74.005, 74.002],
    [74.002, 73.996, 73.993, 74.015, 74.009],
    [73.992, 74.007, 74.015, 73.989, 74.014],
    [74.009, 73.994, 73.997, 73.985, 73.993],
    [73.995, 74.006, 73.994, 74.000, 74.005],
    [73.985, 74.003, 73.993, 74.015, 73.988],
    [74.008, 73.995, 74.009, 74.005, 74.004],
    [73.998, 74.000, 73.990, 74.007, 73.995],
    [73.994, 73.998, 73.994, 73.995, 73.990],
    [74.004, 74.000, 74.007, 74.000, 73.996],
    [73.983, 74.002, 73.998, 73.997, 74.012],
    [74.006, 73.967, 73.994, 74.000, 73.984],
    [74.012, 74.014, 73.998, 73.999, 74.007],
    [74.000, 73.984, 74.005, 73.998, 73.996],
    [73.994, 74.012, 73.986, 74.005, 74.007],
    [74.006, 74.010, 74.018, 74.003, 74.000],
    [73.984, 74.002, 74.003, 74.005, 73.997],
    [74.000, 74.010, 74.013, 74.020, 74.003],
    [73.982, 74.001, 74.015, 74.005, 73.996],
    [74.004, 73.999, 73.990, 74.006, 74.009],
    [74.010, 73.989, 73.990, 74.009, 74.014],
    [74.015, 74.008, 73.993, 74.000, 74.010],
    [73.982, 73.984, 73.995, 74.017, 74.013],
]
# Columnas x̄ y R de la tabla 6.3
PISTON_XBAR = [74.010, 74.001, 74.008, 74.003, 74.003, 73.996, 74.000, 73.997, 74.004, 73.998,
               73.994, 74.001, 73.998, 73.990, 74.006, 73.997, 74.001, 74.007, 73.998, 74.009,
               74.000, 74.002, 74.002, 74.005, 73.998]
PISTON_R = [0.038, 0.019, 0.036, 0.022, 0.026, 0.024, 0.012, 0.030, 0.014, 0.017, 0.008, 0.011,
            0.029, 0.039, 0.016, 0.021, 0.026, 0.018, 0.021, 0.020, 0.033, 0.019, 0.025, 0.022, 0.035]

MORTGAGE = [310, 288, 297, 298, 307, 303, 294, 297, 308, 306,
            294, 299, 297, 299, 314, 295, 293, 306, 301, 304]


# --- transcripción -------------------------------------------------------------


def test_piston_transcription_reproduces_book_columns():
    st = V.subgroup_statistics(V.as_matrix(PISTON, "xbar_r"))
    assert np.round(st.means, 3).tolist() == PISTON_XBAR
    assert np.round(st.ranges, 3).tolist() == PISTON_R
    assert sum(PISTON_R) == pytest.approx(0.581)  # total publicado de la columna R


# --- X-barra-R -----------------------------------------------------------------


def test_xbar_r_piston_rings():
    est = V.estimate_xbar_r(PISTON)
    assert est.mu == pytest.approx(74.001, abs=5e-4)
    assert est.dispersion_bar == pytest.approx(0.023, abs=5e-4)
    # publicado: 0.023/2.326 = 0.0099; sin redondear R̄ = 0.02324 da 0.00999
    assert est.sigma == pytest.approx(0.0099, abs=1.5e-4)
    assert est.sigma_method == "rbar_d2" and est.subgroup_size == 5 and est.points_used == 25
    xb, r = V.xbar_r_limits(est.mu, est.sigma, 5)
    assert float(xb.ucl) == pytest.approx(74.014, abs=1e-3)
    assert float(xb.lcl) == pytest.approx(73.988, abs=1e-3)
    assert float(xb.center) == pytest.approx(74.001, abs=5e-4)
    assert float(r.ucl) == pytest.approx(0.049, abs=5e-4)
    assert float(r.lcl) == 0.0
    assert xb.symmetric and not r.symmetric
    # Con los intermedios redondeados del libro (x̿ = 74.001, R̄ = 0.023):
    xb_b, r_b = V.xbar_r_limits(74.001, 0.023 / K.d2(5), 5)
    assert round(float(xb_b.ucl), 3) == 74.014
    assert round(float(xb_b.lcl), 3) == 73.988
    assert round(float(r_b.ucl), 3) == 0.049


def test_xbar_r_equals_classic_factor_formulas():
    """mu ± L·sigma/sqrt(n) con sigma = R̄/d2 es exactamente x̿ ± A2·R̄, y
    (d2 ± 3 d3)·sigma es D4·R̄, D3·R̄ (Montgomery, sección 6.2.1)."""
    est = V.estimate_xbar_r(PISTON)
    xb, r = V.xbar_r_limits(est.mu, est.sigma, 5)
    rbar = est.dispersion_bar
    assert float(xb.ucl) == pytest.approx(est.mu + K.A2(5) * rbar, rel=1e-12)
    assert float(r.ucl) == pytest.approx(K.D4(5) * rbar, rel=1e-12)
    assert float(r.center) == pytest.approx(rbar, rel=1e-12)
    # n = 7: D3 > 0
    xb7, r7 = V.xbar_r_limits(10.0, 2.0, 7)
    rbar7 = K.d2(7) * 2.0
    assert float(r7.lcl) == pytest.approx(K.D3(7) * rbar7, rel=1e-12)
    assert float(r7.ucl) == pytest.approx(K.D4(7) * rbar7, rel=1e-12)


# --- X-barra-S -----------------------------------------------------------------


def test_xbar_s_piston_rings():
    est = V.estimate_xbar_s(PISTON)
    assert est.dispersion_bar == pytest.approx(0.0094, abs=5e-5)
    assert est.sigma == pytest.approx(0.0100, abs=5e-5)             # 0.0094/0.9400
    xb, s = V.xbar_s_limits(est.mu, est.sigma, 5)
    assert float(xb.ucl) == pytest.approx(74.014, abs=1e-3)
    assert float(xb.lcl) == pytest.approx(73.988, abs=1e-3)
    xb_b, s_b = V.xbar_s_limits(74.001, 0.0094 / K.c4(5), 5)
    assert round(float(xb_b.ucl), 3) == 74.014
    assert round(float(xb_b.lcl), 3) == 73.988
    assert round(float(s_b.ucl), 4) == 0.0196
    assert float(s.ucl) == pytest.approx(0.0196, abs=5e-5)
    assert float(s.lcl) == 0.0
    assert float(s.center) == pytest.approx(est.dispersion_bar, rel=1e-12)
    assert float(xb.ucl) == pytest.approx(est.mu + K.A3(5) * est.dispersion_bar, rel=1e-12)
    assert float(s.ucl) == pytest.approx(K.B4(5) * est.dispersion_bar, rel=1e-12)


def test_s_limits_with_positive_lcl():
    # n = 10: B3 = 0.284 > 0. Esperado calculado con la fórmula (no publicado).
    s = V.s_limits(1.0, 10)
    c = K.c4(10)
    assert float(s.lcl) == pytest.approx(c - 3 * math.sqrt(1 - c * c))
    assert float(s.lcl) == pytest.approx(K.B5(10))


# --- I-MR ----------------------------------------------------------------------


def test_i_mr_mortgage_costs():
    est = V.estimate_i_mr(MORTGAGE)
    assert est.mu == pytest.approx(300.5)
    assert est.dispersion_bar == pytest.approx(7.79, abs=5e-3)
    assert est.dispersion_bar == pytest.approx(148 / 19)  # suma de los 19 MR = 148
    i, mr = V.i_mr_limits(est.mu, est.sigma)
    # El libro usa d2 = 1.128 (aquí 1.128379): 321.22 frente a 321.21.
    assert float(i.ucl) == pytest.approx(321.22, abs=0.015)
    assert float(i.lcl) == pytest.approx(279.78, abs=0.015)
    assert float(mr.ucl) == pytest.approx(25.45, abs=0.01)
    assert float(mr.lcl) == 0.0
    assert float(mr.center) == pytest.approx(est.dispersion_bar)


def test_moving_ranges():
    assert V.moving_ranges([1, 4, 2, 2]).tolist() == [3, 2, 0]


def test_i_mr_exclusion_drops_both_adjacent_moving_ranges():
    x = [10, 11, 30, 12, 11, 10]
    est = V.estimate_i_mr(x, excluded=[2])
    # MR retenidos: |11-10| = 1, |11-12| = 1, |10-11| = 1  (se omiten |30-11| y |12-30|)
    assert est.dispersion_bar == pytest.approx(1.0)
    assert est.mu == pytest.approx((10 + 11 + 12 + 11 + 10) / 5)
    assert est.points_used == 5


def test_i_mr_needs_one_consecutive_pair():
    with pytest.raises(SPCInputError) as exc:
        V.estimate_i_mr([1, 2, 3, 4, 5], excluded=[1, 3, 4])  # quedan 0 y 2: no consecutivos
    assert exc.value.code == "insufficient_data"


def test_i_mr_accepts_list_of_singletons():
    assert V.estimate_i_mr([[v] for v in MORTGAGE]).mu == pytest.approx(300.5)


# --- casos límite --------------------------------------------------------------


def test_minimum_subgroup_size_two():
    est = V.estimate_xbar_r([[1.0, 3.0], [2.0, 2.0], [4.0, 6.0]])
    # R̄ = (2 + 0 + 2)/3; sigma = R̄/d2(2). Esperado calculado a mano.
    assert est.dispersion_bar == pytest.approx(4 / 3)
    assert est.sigma == pytest.approx((4 / 3) / 1.128379, rel=1e-6)
    xb, r = V.xbar_r_limits(est.mu, est.sigma, 2)
    assert float(xb.ucl) == pytest.approx(est.mu + K.A2(2) * 4 / 3)
    assert float(r.ucl) == pytest.approx(K.D4(2) * 4 / 3)


def test_all_values_equal_sigma_zero():
    data = [[5.0, 5.0, 5.0]] * 4
    for est in (V.estimate_xbar_r(data), V.estimate_xbar_s(data)):
        assert est.sigma == 0.0 and est.mu == 5.0
        lo, disp = V.limits_from_params(est.chart_type, est.mu, est.sigma, 3)
        assert float(lo.ucl) == float(lo.lcl) == 5.0
        assert float(disp.ucl) == 0.0
    assert V.estimate_i_mr([7.0] * 5).sigma == 0.0


def test_exclusion_changes_estimate():
    est_all = V.estimate_xbar_r(PISTON)
    est = V.estimate_xbar_r(PISTON, excluded=[13])  # el subgrupo 14 tiene el R más alto
    assert est.points_used == 24
    assert est.dispersion_bar == pytest.approx((0.581 - 0.039) / 24, abs=1e-9)
    assert est.sigma < est_all.sigma


def test_all_but_two_excluded():
    est = V.estimate_xbar_s(PISTON, excluded=list(range(2, 25)))
    st = V.subgroup_statistics(V.as_matrix(PISTON[:2], "xbar_s"))
    assert est.points_used == 2
    assert est.mu == pytest.approx(st.means.mean())
    assert est.sigma == pytest.approx(st.stds.mean() / K.c4(5))
    with pytest.raises(SPCInputError):
        V.estimate_xbar_s(PISTON, excluded=list(range(1, 25)))


@pytest.mark.parametrize("data, chart", [
    ([[1, 2], [1, 2, 3]], "xbar_r"),     # n no constante
    ([[1], [2], [3]], "xbar_r"),          # n = 1
    ([[1, 2], [3, 4]], "i_mr"),           # i_mr con n = 2
    ([[1, 2]], "xbar_s"),                 # un solo subgrupo
    ([[1, float("nan")], [1, 2]], "xbar_r"),
    ([list(range(26))] * 3, "xbar_r"),    # n > 25
])
def test_invalid_inputs(data, chart):
    with pytest.raises(SPCInputError):
        V.as_matrix(data, chart)


def test_large_n_warns_for_range():
    data = np.random.default_rng(1).normal(size=(20, 12)).tolist()
    est = V.estimate_xbar_r(data)
    assert any("X-barra-S" in w for w in est.warnings)


def test_rebuild_limits_with_other_n():
    """Fase II con otro n: mismos mu y sigma, límites con el n nuevo (cálculo a mano)."""
    xb3, r3 = V.xbar_r_limits(74.0, 0.01, 3)
    assert float(xb3.ucl) == pytest.approx(74.0 + 3 * 0.01 / math.sqrt(3))
    assert float(r3.center) == pytest.approx(K.d2(3) * 0.01)
    assert float(r3.ucl) == pytest.approx((K.d2(3) + 3 * K.d3(3)) * 0.01)
