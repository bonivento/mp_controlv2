"""Pruebas de attributes.py: p, np, c, u y el asistente de selección.

Casos de libro (Montgomery, *Introduction to Statistical Quality Control*,
cap. 7, numeración de la 6.ª ed.):

1. Latas de jugo de naranja concentrado, ejemplo 7.1, tabla 7.1: 30 muestras de
   n = 50. Publicado: p̄ = 0.2313, LCS = 0.4102, LCI = 0.0524; las muestras 15 y
   23 quedan fuera. Límites revisados sin ellas: p̄ = 0.2150, LCS = 0.3893,
   LCI = 0.0407, y la muestra 21 queda por encima del LCS revisado.
2. Tarjetas de circuito impreso, ejemplo 7.3, tabla 7.7: 26 muestras de 100
   tarjetas. Publicado: c̄ = 19.85, LCS = 33.22, LCI = 6.48; fuera las muestras
   6 y 20. Revisados sin ellas: c̄ = 19.67, LCS = 32.97, LCI = 6.36.
3. Computadores personales, ejemplo 7.4 (u con n = 5 computadores): 20 muestras.
   Publicado: ū = 1.93, LCS = 3.79, LCI = 0.07, proceso bajo control.
4. p con tamaño variable, sección 7.2.2, tabla 7.4: 25 días, n entre 80 y 120.
   Publicado: p̄ = 0.096. Los límites por punto se calculan aquí con la
   fórmula (no se usan los valores impresos del libro).

Las sumas de cada tabla (347, 516, 193, 234 y 2450) se comprueban para
detectar errores de transcripción.
"""

import math

import numpy as np
import pytest

from app.spc import attributes as A
from app.spc.constants import SPCInputError

OJ_D = [12, 15, 8, 10, 4, 7, 16, 9, 14, 10, 5, 6, 17, 12, 22,
        8, 10, 5, 13, 11, 20, 18, 24, 15, 9, 12, 7, 13, 9, 6]
OJ_N = [50] * 30

PCB_C = [21, 24, 16, 12, 15, 5, 28, 20, 31, 25, 20, 24, 16, 19, 10,
         17, 13, 22, 18, 39, 30, 24, 16, 19, 17, 15]

PC_C = [10, 12, 8, 14, 10, 16, 11, 7, 10, 15, 9, 5, 7, 11, 12, 6, 8, 10, 7, 5]
PC_N = [5] * 20

VAR_N = [100, 80, 80, 100, 110, 110, 100, 100, 90, 90, 110, 120, 120,
         120, 110, 80, 80, 80, 90, 100, 100, 100, 100, 90, 90]
VAR_D = [12, 8, 6, 9, 10, 12, 11, 16, 10, 6, 20, 15, 9, 8, 6, 8, 10, 7, 5, 8, 5, 8, 10, 6, 9]


def test_transcription_totals():
    assert sum(OJ_D) == 347
    assert sum(PCB_C) == 516
    assert sum(PC_C) == 193
    assert sum(VAR_D) == 234 and sum(VAR_N) == 2450


# --- p -------------------------------------------------------------------------


def test_p_chart_orange_juice_trial_limits():
    est = A.estimate_p(OJ_D, OJ_N)
    assert est.value == pytest.approx(0.2313, abs=5e-5)
    assert est.subgroup_size == 50
    lim = A.p_limits(est.value, OJ_N)
    assert lim.ucl[0] == pytest.approx(0.4102, abs=5e-5)
    assert lim.lcl[0] == pytest.approx(0.0524, abs=5e-5)
    p = A.plotted_values("p", np.array(OJ_D, float), np.array(OJ_N, float))
    out = np.flatnonzero((p > lim.ucl) | (p < lim.lcl)).tolist()
    assert out == [14, 22]  # muestras 15 y 23
    assert lim.symmetric


def test_p_chart_orange_juice_revised_limits():
    est = A.estimate_p(OJ_D, OJ_N, excluded=[14, 22])
    assert est.value == pytest.approx(0.2150, abs=5e-5)  # 301/1400
    assert est.points_used == 28
    lim = A.p_limits(est.value, OJ_N)
    assert lim.ucl[0] == pytest.approx(0.3893, abs=5e-5)
    assert lim.lcl[0] == pytest.approx(0.0407, abs=5e-5)
    assert OJ_D[20] / 50 > lim.ucl[20]  # la muestra 21 queda fuera del LCS revisado


def test_p_chart_variable_size_per_point_limits():
    est = A.estimate_p(VAR_D, VAR_N)
    assert est.value == pytest.approx(0.096, abs=5e-4)
    assert est.value == pytest.approx(234 / 2450)   # promedio ponderado, no media de p_i
    assert est.subgroup_size is None
    lim = A.p_limits(est.value, VAR_N)
    p = est.value
    for i, n in enumerate(VAR_N):  # esperado calculado con la fórmula de la sección 7.2.2
        half = 3 * math.sqrt(p * (1 - p) / n)
        assert lim.ucl[i] == pytest.approx(p + half)
        assert lim.lcl[i] == pytest.approx(max(0.0, p - half))
    # Con n = 80 el LCI es negativo y se trunca en 0: las zonas no aplican.
    assert lim.lcl[1] == 0.0 and lim.lcl[0] > 0.0
    assert not lim.symmetric
    assert any("truncó en 0" in w for w in A.truncation_warnings("p", lim))


def test_p_upper_limit_truncated_at_one():
    lim = A.p_limits(0.5, [2, 2, 2])
    assert np.all(lim.ucl == 1.0) and np.all(lim.lcl == 0.0)
    assert not lim.symmetric


# --- np ------------------------------------------------------------------------


def test_np_chart_orange_juice():
    """Esperado calculado a mano: n·p̄ = 50·347/1500 = 11.567;
    LCS/LCI = 11.567 ± 3·sqrt(11.567·(1 - 0.23133)) = 20.51 / 2.62."""
    est = A.estimate_np(OJ_D, OJ_N)
    lim = A.np_limits(est.value, 50, 30)
    assert lim.center[0] == pytest.approx(50 * 347 / 1500)
    assert lim.ucl[0] == pytest.approx(20.51, abs=5e-3)
    assert lim.lcl[0] == pytest.approx(2.62, abs=5e-3)
    # np es p escalado por n
    plim = A.p_limits(est.value, OJ_N)
    assert lim.ucl[0] == pytest.approx(50 * plim.ucl[0])


def test_np_requires_constant_size():
    with pytest.raises(SPCInputError, match="constante"):
        A.estimate_np([1, 2, 3], [50, 50, 60])


# --- c -------------------------------------------------------------------------


def test_c_chart_circuit_boards():
    est = A.estimate_c(PCB_C)
    assert est.value == pytest.approx(19.85, abs=5e-3)
    lim = A.c_limits(est.value, 26)
    # El libro redondea c̄ a 19.85 antes de calcular (19.85 + 3·sqrt(19.85) = 33.22);
    # con c̄ = 516/26 = 19.846 sin redondear, LCS = 33.21.
    assert lim.ucl[0] == pytest.approx(33.22, abs=0.01)
    assert lim.lcl[0] == pytest.approx(6.48, abs=5e-3)
    assert round(float(A.c_limits(19.85, 1).ucl[0]), 2) == 33.22
    c = np.array(PCB_C, float)
    assert np.flatnonzero((c > lim.ucl) | (c < lim.lcl)).tolist() == [5, 19]


def test_c_chart_circuit_boards_revised():
    est = A.estimate_c(PCB_C, excluded=[5, 19])
    assert est.value == pytest.approx(19.67, abs=5e-3)
    lim = A.c_limits(est.value, 26)
    assert lim.ucl[0] == pytest.approx(32.97, abs=5e-3)
    assert lim.lcl[0] == pytest.approx(6.36, abs=5e-3)


def test_c_rejects_variable_sizes():
    with pytest.raises(SPCInputError, match="u"):
        A.validate_attribute_data("c", [1, 2, 3], [1, 2, 1])
    A.validate_attribute_data("c", [1, 2, 3], [2, 2, 2])  # constante: se acepta


# --- u -------------------------------------------------------------------------


def test_u_chart_personal_computers():
    est = A.estimate_u(PC_C, PC_N)
    assert est.value == pytest.approx(1.93)
    lim = A.u_limits(est.value, PC_N)
    assert lim.ucl[0] == pytest.approx(3.79, abs=5e-3)
    assert lim.lcl[0] == pytest.approx(0.07, abs=5e-3)
    u = A.plotted_values("u", np.array(PC_C, float), np.array(PC_N, float))
    assert np.all((u <= lim.ucl) & (u >= lim.lcl))


def test_u_chart_fractional_variable_sizes():
    """Esperado a mano: ū = 12/6 = 2; con n = 0.5 la mitad del ancho es 3·sqrt(2/0.5) = 6."""
    counts, sizes = [2, 4, 6], [0.5, 2.0, 3.5]
    est = A.estimate_u(counts, sizes)
    assert est.value == pytest.approx(2.0)
    assert est.subgroup_size is None
    lim = A.u_limits(est.value, sizes)
    assert lim.ucl[0] == pytest.approx(8.0)
    assert lim.lcl[0] == 0.0
    assert lim.ucl[2] == pytest.approx(2 + 3 * math.sqrt(2 / 3.5))


# --- casos límite --------------------------------------------------------------


def test_zero_counts():
    est = A.estimate_c([0, 0, 0, 0])
    assert est.value == 0.0 and any("c̄ = 0" in w for w in est.warnings)
    lim = A.c_limits(0.0, 4)
    assert np.all(lim.ucl == 0.0) and np.all(lim.lcl == 0.0)
    est = A.estimate_p([0, 0, 0], [20, 20, 20])
    assert est.value == 0.0 and est.warnings
    est = A.estimate_u([0, 3, 0], [1, 1, 1])
    assert est.value == 1.0


def test_single_point_excluded():
    est = A.estimate_c(PCB_C, excluded=[19])
    assert est.value == pytest.approx((516 - 39) / 25)


def test_all_but_two_excluded():
    est = A.estimate_p(OJ_D, OJ_N, excluded=list(range(2, 30)))
    assert est.value == pytest.approx((12 + 15) / 100)
    with pytest.raises(SPCInputError) as exc:
        A.estimate_p(OJ_D, OJ_N, excluded=list(range(1, 30)))
    assert exc.value.code == "insufficient_data"


@pytest.mark.parametrize("chart, counts, sizes", [
    ("p", [1, 2, 3], None),           # falta n
    ("p", [5, 2], [4, 4]),            # D > n
    ("p", [1, -1], [4, 4]),           # negativo
    ("c", [1.5, 2], None),            # no entero
    ("u", [1, 2], [1, 0]),            # n = 0
    ("u", [1, 2], [1]),               # largos distintos
    ("c", [3], None),                 # un solo subgrupo
    ("x", [1, 2], None),
])
def test_invalid_attribute_data(chart, counts, sizes):
    with pytest.raises(SPCInputError):
        A.validate_attribute_data(chart, counts, sizes)


# --- asistente -------------------------------------------------------------------


@pytest.mark.parametrize("counting, constant, expected, alternatives", [
    ("defectives", True, "np", ["p"]),
    ("defectives", False, "p", []),
    ("defects", True, "c", ["u"]),
    ("defects", False, "u", []),
])
def test_recommend_chart(counting, constant, expected, alternatives):
    rec = A.recommend_chart(counting, constant)
    assert rec.chart_type == expected
    assert rec.alternatives == alternatives
    assert len(rec.justification) > 80
    word = "binomial" if counting == "defectives" else "Poisson"
    assert word in rec.justification


def test_recommend_chart_invalid():
    with pytest.raises(SPCInputError):
        A.recommend_chart("defectos", True)
