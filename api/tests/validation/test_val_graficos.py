"""Validación independiente de variables.py, attributes.py y phases.py.

Los esperados se calculan aquí con las fórmulas de Montgomery (cap. 6 y 7)
escritas a mano y con constantes propias (`independiente.py`), no con las
funciones del software. Los datos de libro se toman de las pruebas de los
autores; su transcripción solo se comprueba por consistencia interna (totales y
columnas derivadas), porque no se tiene el libro a mano.
"""

import json
import math
from pathlib import Path

import numpy as np
import pytest

from app.spc import phases
from tests.spc.test_attributes import OJ_D, OJ_N, PC_C, PC_N, PCB_C, VAR_D, VAR_N
from tests.spc.test_variables import MORTGAGE, PISTON, PISTON_R, PISTON_XBAR

from .independiente import c4_por_chi, d2_por_maximo, d3_por_momentos

REF = Path(__file__).resolve().parents[3] / "data" / "referencia"


def _d(n):
    return d2_por_maximo(n), d3_por_momentos(n)


# --------------------------------------------------------------- variables


def test_piston_xbar_r_a_mano():
    x = np.array(PISTON)
    xbb = sum(sum(r) / 5 for r in PISTON) / 25
    rbar = sum(max(r) - min(r) for r in PISTON) / 25
    d2, d3 = _d(5)
    r = phases.phase_one("xbar_r", PISTON)
    xb, rr = r.charts
    assert xb.center[0] == pytest.approx(xbb, abs=1e-12)
    assert xb.ucl[0] == pytest.approx(xbb + 3 * rbar / (d2 * math.sqrt(5)), abs=1e-8)
    assert xb.lcl[0] == pytest.approx(xbb - 3 * rbar / (d2 * math.sqrt(5)), abs=1e-8)
    assert rr.ucl[0] == pytest.approx(rbar * (1 + 3 * d3 / d2), abs=1e-8)
    assert rr.lcl[0] == 0.0  # 1 - 3·d3/d2 < 0 para n = 5
    assert r.limits.params["sigma"] == pytest.approx(rbar / d2, rel=1e-6)
    assert r.in_control
    # consistencia de la transcripción: columnas x̄ y R y total publicado de R
    assert np.round(x.mean(axis=1), 3).tolist() == PISTON_XBAR
    assert sum(PISTON_R) == pytest.approx(0.581)


def test_piston_xbar_s_a_mano():
    s = [float(np.std(r, ddof=1)) for r in PISTON]
    sbar = sum(s) / 25
    c4 = c4_por_chi(5)
    xbb = float(np.mean(PISTON))
    r = phases.phase_one("xbar_s", PISTON)
    xb, ss = r.charts
    assert xb.ucl[0] == pytest.approx(xbb + 3 * sbar / (c4 * math.sqrt(5)), abs=1e-9)
    assert ss.center[0] == pytest.approx(sbar, abs=1e-12)
    assert ss.ucl[0] == pytest.approx(sbar * (1 + 3 * math.sqrt(1 - c4 * c4) / c4), abs=1e-9)
    assert ss.lcl[0] == 0.0


def test_mortgage_i_mr_a_mano():
    x = MORTGAGE
    mr = [abs(b - a) for a, b in zip(x, x[1:])]
    mrbar = sum(mr) / len(mr)
    d2, d3 = _d(2)
    r = phases.phase_one("i_mr", x)
    i, m = r.charts
    assert i.ucl[0] == pytest.approx(sum(x) / 20 + 3 * mrbar / d2, abs=1e-5)
    assert m.ucl[0] == pytest.approx(mrbar * (1 + 3 * d3 / d2), abs=1e-5)
    assert m.indices == list(range(1, 20))


def test_i_mr_exclusion_solo_pares_retenidos():
    x = [5.0, 7.0, 6.0, 40.0, 6.5, 5.5, 7.5, 6.0]
    r = phases.phase_one("i_mr", x, excluded=[(3, "error de registro")])
    # pares retenidos: (0,1) (1,2) (4,5) (5,6) (6,7) -> 2, 1, 1, 2, 1.5
    mrbar = (2 + 1 + 1 + 2 + 1.5) / 5
    mean = (sum(x) - 40.0) / 7
    assert r.limits.params["mr_bar"] == pytest.approx(mrbar)
    assert r.limits.params["mu"] == pytest.approx(mean)
    assert r.charts[0].values[3] == 40.0           # sigue graficado
    assert r.charts[1].excluded == [3, 4]          # MR_3 y MR_4 tocan el excluido
    assert 3 not in r.out_of_control_points


def test_reconstruccion_con_otro_n():
    """Fase II con n distinto: X-barra, R y S con el n nuevo a partir de (μ, σ) congelados."""
    p1 = phases.phase_one("xbar_s", PISTON)
    mu, sigma = p1.limits.params["mu"], p1.limits.params["sigma"]
    rng = np.random.default_rng(1)
    new = (mu + sigma * rng.standard_normal((6, 8))).tolist()
    p2 = phases.phase_two("xbar_s", new, p1.limits)
    c4 = c4_por_chi(8)
    xb, s = p2.charts
    assert xb.ucl[0] == pytest.approx(mu + 3 * sigma / math.sqrt(8), rel=1e-12)
    assert s.center[0] == pytest.approx(c4 * sigma, rel=1e-10)
    assert s.ucl[0] == pytest.approx((c4 + 3 * math.sqrt(1 - c4 * c4)) * sigma, rel=1e-10)
    assert s.lcl[0] == pytest.approx(max(0.0, (c4 - 3 * math.sqrt(1 - c4 * c4)) * sigma), abs=1e-12)
    p1r = phases.phase_one("xbar_r", PISTON)
    p2r = phases.phase_two("xbar_r", [row[:3] for row in PISTON], p1r.limits)
    d2, d3 = _d(3)
    sg = p1r.limits.params["sigma"]
    assert p2r.charts[1].center[0] == pytest.approx(d2 * sg, rel=1e-6)
    assert p2r.charts[1].ucl[0] == pytest.approx((d2 + 3 * d3) * sg, rel=1e-6)


def test_fase_dos_nunca_recalcula():
    p1 = phases.phase_one("xbar_r", PISTON)
    base = phases.phase_two("xbar_r", PISTON, p1.limits)
    otro = phases.phase_two("xbar_r", (np.array(PISTON) * 3 + 10).tolist(), p1.limits)
    for a, b in zip(base.charts, otro.charts):
        assert a.center == b.center and a.ucl == b.ucl and a.lcl == b.lcl
    pa = phases.phase_one("u", PC_C, PC_N)
    for data in ([1, 2, 3], [40, 50, 60]):
        p2 = phases.phase_two("u", data, pa.limits, sizes=[2, 4, 8])
        u = 193 / 100
        assert p2.charts[0].ucl == pytest.approx([u + 3 * math.sqrt(u / k) for k in (2, 4, 8)])


def test_excluidos_salen_del_calculo_no_del_grafico():
    data = [list(r) for r in PISTON]
    data[10] = [v + 0.04 for v in data[10]]
    r = phases.phase_one("xbar_r", data, excluded=[(10, "micrómetro descalibrado")])
    keep = [row for k, row in enumerate(data) if k != 10]
    xbb = float(np.mean([np.mean(g) for g in keep]))
    rbar = float(np.mean([max(g) - min(g) for g in keep]))
    assert r.charts[0].center[0] == pytest.approx(xbb, abs=1e-12)
    assert r.charts[1].center[0] == pytest.approx(rbar, abs=1e-12)
    assert len(r.charts[0].values) == 25 and r.charts[0].values[10] == pytest.approx(np.mean(data[10]))
    assert r.charts[0].excluded == [10] and r.limits.points_used == 24


# --------------------------------------------------------------- atributos


def test_p_jugo_de_naranja_a_mano():
    pbar = sum(OJ_D) / 1500
    half = 3 * math.sqrt(pbar * (1 - pbar) / 50)
    r = phases.phase_one("p", OJ_D, OJ_N)
    assert r.charts[0].ucl[0] == pytest.approx(pbar + half, abs=1e-12)
    assert r.charts[0].lcl[0] == pytest.approx(pbar - half, abs=1e-12)
    assert r.out_of_control_points == [i for i, d in enumerate(OJ_D) if not pbar - half <= d / 50 <= pbar + half]
    pb2 = (sum(OJ_D) - OJ_D[14] - OJ_D[22]) / 1400
    rev = phases.phase_one("p", OJ_D, OJ_N, excluded=[(14, "a"), (22, "b")])
    assert rev.charts[0].ucl[0] == pytest.approx(pb2 + 3 * math.sqrt(pb2 * (1 - pb2) / 50), abs=1e-12)
    assert rev.out_of_control_points == [20]


def test_c_tarjetas_y_u_computadores_a_mano():
    cbar = sum(PCB_C) / 26
    r = phases.phase_one("c", PCB_C)
    assert r.charts[0].ucl[0] == pytest.approx(cbar + 3 * math.sqrt(cbar), abs=1e-12)
    assert r.charts[0].lcl[0] == pytest.approx(cbar - 3 * math.sqrt(cbar), abs=1e-12)
    assert r.out_of_control_points == [5, 19]
    u = sum(PC_C) / sum(PC_N)
    r = phases.phase_one("u", PC_C, PC_N)
    assert r.charts[0].ucl[0] == pytest.approx(u + 3 * math.sqrt(u / 5), abs=1e-12)
    assert r.in_control


def test_p_tamano_variable_tabla_7_4():
    """Duda 7. Los totales (234 y 2450) coinciden con p̄ = 0.096 publicado; el resto de la
    transcripción no se puede verificar contra el libro. Con estos datos la muestra 11
    (20/110 = 0.1818) supera su LCS (0.1796): la conclusión es correcta para estos datos."""
    pbar = 234 / 2450
    ucl11 = pbar + 3 * math.sqrt(pbar * (1 - pbar) / 110)
    assert VAR_D[10] / VAR_N[10] > ucl11
    r = phases.phase_one("p", VAR_D, VAR_N)
    assert r.charts[0].ucl[10] == pytest.approx(ucl11, abs=1e-12)
    assert 10 in r.out_of_control_points
    for i, n in enumerate(VAR_N):
        assert r.charts[0].lcl[i] == pytest.approx(max(0.0, pbar - 3 * math.sqrt(pbar * (1 - pbar) / n)))


def test_truncamientos():
    r = phases.phase_one("p", [1, 0, 2, 1], [10, 10, 10, 10], rules=["WE1", "WE2"])
    assert r.charts[0].lcl == [0.0] * 4 and "WE2" in r.charts[0].rules_skipped
    r = phases.phase_one("c", [0, 1, 0, 2, 1])
    assert r.charts[0].lcl == [0.0] * 5


# --------------------------------------------------------------- casos de data/referencia


def _ref(name):
    return json.loads((REF / name).read_text(encoding="utf-8"))


def test_referencia_xbar_r_y_xbar_s():
    """Los JSON usan A2 = 1.023, D4 = 2.574, A3 = 1.954, B4 = 2.568 (tres decimales):
    son los valores de tabla correctos redondeados; los límites exactos difieren en ≤ 0.0015."""
    sg = [s["x"] for s in _ref("xbar_r_n3.json")["datos"]["subgrupos"]]
    d2, d3 = _d(3)
    c4 = c4_por_chi(3)
    assert 3 / (d2 * math.sqrt(3)) == pytest.approx(1.023, abs=5e-4)
    assert 1 + 3 * d3 / d2 == pytest.approx(2.574, abs=1e-3)   # exacto 2.57459: la tabla trunca
    assert 3 / (c4 * math.sqrt(3)) == pytest.approx(1.954, abs=5e-4)
    assert 1 + 3 * math.sqrt(1 - c4 * c4) / c4 == pytest.approx(2.568, abs=5e-4)
    r = phases.phase_one("xbar_r", sg)
    assert r.charts[0].ucl[0] == pytest.approx(12 + 2.5 * 3 / (d2 * math.sqrt(3)), abs=1e-6)
    assert r.charts[0].ucl[0] == pytest.approx(_ref("xbar_r_n3.json")["esperado"]["ucl_xbar"], abs=1e-3)
    assert r.charts[1].ucl[0] == pytest.approx(_ref("xbar_r_n3.json")["esperado"]["ucl_r"], abs=2e-3)
    assert r.out_of_control_points == [3]
    s = phases.phase_one("xbar_s", sg)
    assert s.charts[0].ucl[0] == pytest.approx(_ref("xbar_s_n3.json")["esperado"]["ucl_xbar"], abs=1e-3)
    assert s.charts[1].ucl[0] == pytest.approx(_ref("xbar_s_n3.json")["esperado"]["ucl_s"], abs=1e-3)
    assert s.out_of_control_points == [3]


def test_referencia_i_mr_np_c_p_u():
    j = _ref("i_mr.json")
    r = phases.phase_one("i_mr", j["datos"]["valores"])
    d2, _ = _d(2)
    assert r.charts[0].ucl[0] == pytest.approx(12 + 3 * 2.5 / d2, abs=1e-6)   # 18.6467; JSON 18.65 (E2 = 2.66)
    assert r.charts[0].ucl[0] == pytest.approx(j["esperado"]["ucl_i"], abs=5e-3)
    j = _ref("np.json")
    r = phases.phase_one("np", j["datos"]["defectuosos"], [100] * 5)
    assert r.charts[0].ucl[0] == pytest.approx(6.6 + 3 * math.sqrt(6.6 * 0.934), abs=1e-9)  # 14.04846
    assert r.charts[0].ucl[0] == pytest.approx(j["esperado"]["ucl"], abs=5e-5)          # JSON 14.04849
    assert r.out_of_control_points == [4]
    j = _ref("c.json")
    r = phases.phase_one("c", j["datos"]["defectos"])
    assert r.charts[0].ucl[0] == pytest.approx(j["esperado"]["ucl"], abs=1e-5)
    assert r.out_of_control_points == [7]
    j = _ref("p.json")
    m = j["datos"]["muestras"]
    r = phases.phase_one("p", [s["defectuosos"] for s in m], [s["n"] for s in m])
    exact80 = 0.0625 + 3 * math.sqrt(0.0625 * 0.9375 / 80)   # 0.1436899; JSON 0.1436922
    assert r.charts[0].ucl[4] == pytest.approx(exact80, abs=1e-12)
    assert r.charts[0].ucl == pytest.approx(j["esperado"]["ucl_por_muestra"], abs=5e-6)
    assert r.out_of_control_points == [4]
    j = _ref("u.json")
    m = j["datos"]["muestras"]
    r = phases.phase_one("u", [s["defectos"] for s in m], [s["unidades"] for s in m])
    assert r.charts[0].ucl == pytest.approx(j["esperado"]["ucl_por_muestra"], abs=1e-6)
    assert r.out_of_control_points == [3]
