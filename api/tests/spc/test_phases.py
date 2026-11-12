"""Pruebas de phases.py: Fase I (exclusiones, congelar) y Fase II (sin recalcular).

Se reutilizan los casos de libro de test_variables.py y test_attributes.py
(Montgomery, cap. 6 y 7). El caso de Fase II del jugo de naranja usa las 24
muestras tomadas después del ajuste de la máquina (Montgomery, ejemplo 7.1,
tabla 7.2, 6.ª ed.; total 133 defectuosos en 1200 latas). Para esas muestras
el esperado se calcula aquí con la fórmula contra los límites congelados
(p̄ = 0.215), no se toma del libro.
"""

import math

import numpy as np
import pytest

from app.schemas.charts import ChartResponse
from app.schemas.common import FrozenLimits
from app.spc import constants as K
from app.spc.constants import SPCInputError
from app.spc.phases import (
    Exclusion,
    FrozenParameters,
    attributes_phase_one,
    attributes_phase_two,
    phase_one,
    phase_two,
    variables_phase_one,
    variables_phase_two,
)
from app.spc.rules import LIMIT_RULES, RULE_IDS, ZONE_RULES

from .test_attributes import OJ_D, OJ_N, PCB_C, PC_C, PC_N, VAR_D, VAR_N
from .test_variables import MORTGAGE, PISTON

OJ_PHASE2 = [9, 6, 12, 5, 6, 4, 6, 3, 7, 6, 2, 4, 3, 6, 5, 4, 8, 5, 6, 7, 5, 6, 3, 5]

INTERPRETATION = {"summary": "prueba", "findings": [], "warnings": []}


def to_response(result):
    return ChartResponse.model_validate({**result.to_contract(), "interpretation": INTERPRETATION})


# --- Fase I: atributos -----------------------------------------------------------


def test_phase_one_p_trial_then_revised():
    trial = phase_one("p", OJ_D, OJ_N)
    assert trial.out_of_control_points == [14, 22]
    assert not trial.in_control
    assert trial.limits.params["p_bar"] == pytest.approx(0.2313, abs=5e-5)

    revised = phase_one("p", OJ_D, OJ_N, excluded=[
        {"index": 14, "cause": "Lote nuevo de cartón"},
        {"index": 22, "cause": "Operario sin experiencia", "label": "23"},
    ])
    panel = revised.charts[0]
    assert len(panel.values) == 30                     # se grafican todos
    assert panel.excluded == [14, 22]
    assert panel.values[14] == pytest.approx(22 / 50)
    assert panel.ucl[0] == pytest.approx(0.3893, abs=5e-5)
    assert panel.lcl[0] == pytest.approx(0.0407, abs=5e-5)
    # 15 y 23 están sobre el LCS pero excluidos: no cuentan. La 21 sí (Montgomery, ej. 7.1).
    assert revised.out_of_control_points == [20]
    fz = revised.limits
    assert fz.params == {"p_bar": pytest.approx(301 / 1400)}
    assert fz.points_used == 28 and fz.subgroup_size == 50 and fz.sigma_method is None
    assert [e.cause for e in fz.excluded] == ["Lote nuevo de cartón", "Operario sin experiencia"]
    to_response(revised)


def test_phase_two_p_uses_frozen_limits():
    revised = phase_one("p", OJ_D, OJ_N, excluded=[(14, "cartón"), (22, "operario")])
    new = phase_two("p", OJ_PHASE2, revised.limits, sizes=[50] * 24, rules={"enabled": ["WE1", "WE4"]})
    panel = new.charts[0]
    p_bar = 0.215
    half = 3 * math.sqrt(p_bar * (1 - p_bar) / 50)
    assert all(c == pytest.approx(p_bar) for c in panel.center)
    assert panel.ucl[0] == pytest.approx(p_bar + half)
    assert panel.lcl[0] == pytest.approx(p_bar - half)
    assert new.limits is revised.limits                # se devuelven los mismos
    # 2/50 = 0.04 < LCI 0.0407 en la muestra 11 de la Fase II (índice 10)
    we1 = [v.index for v in panel.violations if v.rule == "WE1"]
    assert we1 == [10]
    # desde el índice 3 todos los puntos quedan bajo p̄ = 0.215: WE4 se completa en el índice 10
    we4 = [v.index for v in panel.violations if v.rule == "WE4"]
    assert we4[0] == 10 and we4 == list(range(10, 24))
    assert new.phase == "II"
    to_response(new)


def test_phase_one_c_with_exclusions():
    r = phase_one("c", PCB_C, excluded=[(5, "Control de temperatura"), (19, "Inspector nuevo")])
    assert r.limits.params["c_bar"] == pytest.approx(472 / 24)
    assert r.charts[0].ucl[0] == pytest.approx(32.97, abs=5e-3)
    assert r.in_control
    assert r.limits.subgroup_size is None
    to_response(r)


def test_phase_one_u_in_control():
    r = phase_one("u", PC_C, PC_N, rules={"enabled": list(RULE_IDS)})
    assert r.limits.params == {"u_bar": pytest.approx(1.93)}
    assert r.charts[0].lcl[0] == pytest.approx(0.07, abs=5e-3)
    assert r.charts[0].rules_applied == list(RULE_IDS)  # LCI > 0: zonas simétricas
    to_response(r)


def test_phase_one_p_variable_size_skips_zone_rules():
    r = phase_one("p", VAR_D, VAR_N, rules=["WE1", "WE2", "N4"])
    panel = r.charts[0]
    assert r.limits.subgroup_size is None
    assert len(set(round(u, 12) for u in panel.ucl)) == 5   # cinco tamaños distintos
    assert panel.rules_applied == ["WE1", "N4"]
    assert "WE2" in panel.rules_skipped
    assert any("WE2 no se aplica" in w for w in r.warnings)
    assert any("truncó en 0" in w for w in r.warnings)
    # N4 se aplica con nota de que no depende de la asimetría
    assert any(w.startswith("Panel P: El gráfico es de conteos con límites asimétricos; la regla N4 depende solo")
               for w in r.warnings)
    to_response(r)


def test_phase_two_np_with_other_constant_n():
    p1 = phase_one("np", OJ_D, OJ_N, excluded=[(14, "a"), (22, "b")])
    p2 = phase_two("np", [5, 8, 6], p1.limits, sizes=[40, 40, 40])
    assert p2.charts[0].center[0] == pytest.approx(40 * 0.215)
    assert any("n = 40" in w for w in p2.warnings)


def test_zero_counts_phase_one():
    r = phase_one("c", [0, 0, 0, 0, 0], rules=list(RULE_IDS))
    assert r.in_control
    assert r.charts[0].ucl == [0.0] * 5
    assert any("c̄ = 0" in w for w in r.warnings)
    to_response(r)


# --- Fase I y II: variables -------------------------------------------------------


def test_phase_one_xbar_r_piston():
    r = variables_phase_one("xbar_r", PISTON, rules=["WE1", "WE2", "WE3", "WE4"])
    xbar, rng = r.charts
    assert (xbar.name, rng.name) == ("xbar", "r")
    assert xbar.ucl[0] == pytest.approx(74.014, abs=1e-3)
    assert rng.ucl[0] == pytest.approx(0.049, abs=5e-4)
    assert r.in_control                                         # Montgomery: en control
    assert r.limits.sigma_method == "rbar_d2" and r.limits.subgroup_size == 5
    assert set(r.limits.params) >= {"mu", "sigma"}
    # en el panel R solo se aplican las reglas sin zonas
    assert rng.rules_applied == ["WE1", "WE4"]
    assert set(rng.rules_skipped) == {"WE2", "WE3"}
    assert xbar.rules_applied == ["WE1", "WE2", "WE3", "WE4"]
    to_response(r)


def test_phase_one_xbar_s_piston():
    r = phase_one("xbar_s", PISTON)
    assert r.charts[1].name == "s"
    assert r.charts[1].ucl[0] == pytest.approx(0.0196, abs=5e-5)
    assert r.limits.sigma_method == "sbar_c4"
    to_response(r)


def test_phase_one_i_mr_mortgage():
    r = phase_one("i_mr", MORTGAGE, rules=list(RULE_IDS))
    i, mr = r.charts
    assert len(i.values) == 20 and len(mr.values) == 19
    assert mr.indices == list(range(1, 20))
    assert mr.labels[0] == "2"
    assert r.limits.subgroup_size == 1 and r.limits.sigma_method == "mrbar_d2"
    # H5: en MR solo se evalúa el punto fuera de límites (correlación serial).
    assert mr.rules_applied == list(LIMIT_RULES)
    assert set(mr.rules_skipped) == set(RULE_IDS) - set(LIMIT_RULES)
    assert all("correlacionados" in m for m in mr.rules_skipped.values())
    assert i.rules_applied == list(RULE_IDS)
    assert not any(w.startswith("Panel MR:") and "falsas alarmas es mayor" in w for w in r.warnings)
    to_response(r)


def _mr_run_below_center():
    # 12 individuales con saltos chicos (MR = 0.1) y dos saltos grandes al inicio:
    # MR̄ = (2·3 + 9·0.1)/11 = 0.627; los 9 MR finales quedan bajo la LC.
    return [10.0, 13.0, 10.0] + [10.0 + 0.1 * (k % 2) for k in range(1, 10)]


def test_mr_panel_never_flags_runs():
    x = _mr_run_below_center()
    r = phase_one("i_mr", x, rules=["WE1", "WE4", "N2", "N3"])
    mr = r.charts[1]
    assert mr.rules_applied == ["WE1"]
    assert set(mr.rules_skipped) == {"WE4", "N2", "N3"}
    assert all(v.rule == "WE1" for v in mr.violations)
    assert sum("Panel MR:" in w for w in r.warnings) == 3     # un motivo por regla omitida
    # el panel I sí evalúa las rachas (es simétrico): sin advertencia de asimetría
    assert r.charts[0].rules_applied == ["WE1", "WE4", "N2", "N3"]
    assert not any("asimétrico" in w and w.startswith("Panel I:") for w in r.warnings)
    to_response(r)


@pytest.mark.parametrize("chart", ["xbar_r", "xbar_s"])
def test_dispersion_panel_warns_once_for_side_run_rules(chart):
    r = phase_one(chart, PISTON, rules=list(RULE_IDS))
    disp = r.charts[1].name.upper()
    asym = [w for w in r.warnings if "falsas alarmas es mayor que la nominal" in w]
    assert len(asym) == 1 and asym[0].startswith(f"Panel {disp}: Las reglas WE4 y N2 se aplicaron")
    assert "N3 y N4 dependen solo del orden" in asym[0]
    assert r.charts[1].warnings == [asym[0].removeprefix(f"Panel {disp}: ")]
    assert r.charts[0].warnings == []                           # X-barra es simétrico
    # sin reglas de racha pedidas no hay advertencia
    plain = phase_one(chart, PISTON, rules=["WE1", "WE2"])
    assert not any("solo del orden" in w or "mayor que la nominal" in w for w in plain.warnings)


def test_truncated_attribute_panel_warns_for_side_runs():
    # c̄ = 1 da LCI = 1 - 3 < 0, truncado: panel asimétrico.
    r = phase_one("c", [1, 0, 2, 1, 0, 1, 2, 1, 0, 2], rules=["WE1", "WE4"])
    assert r.charts[0].rules_applied == ["WE1", "WE4"]
    asym = [w for w in r.warnings if "es de conteos con límites asimétricos" in w]
    assert len(asym) == 1 and asym[0].startswith("Panel C: La regla WE4 se aplicó")
    assert "mayor que la nominal" not in asym[0]            # H19: en conteos puede ser mucho menor
    assert "distinta de la nominal" in asym[0] and "cortan la racha" in asym[0]
    p2 = phase_two("c", [0, 0, 0, 0, 0, 0, 0, 0], r.limits, rules=["WE1", "WE4"])
    assert [v.index for v in p2.charts[0].violations] == [7]    # WE4 sigue señalando
    assert sum("distinta de la nominal" in w for w in p2.warnings) == 1


def test_untruncated_attribute_panel_has_no_asymmetry_warning():
    r = phase_one("u", PC_C, PC_N, rules=list(RULE_IDS))
    assert not any("mayor que la nominal" in w or "distinta de la nominal" in w for w in r.warnings)


def test_single_excluded_point_marked_on_both_panels():
    data = [list(row) for row in PISTON]
    data[3] = [v + 0.05 for v in data[3]]  # desplaza el subgrupo 4: queda fuera
    r_all = phase_one("xbar_r", data)
    assert 3 in r_all.out_of_control_points
    r = phase_one("xbar_r", data, excluded=[Exclusion(3, "Calibración del micrómetro")])
    assert r.charts[0].excluded == [3] and r.charts[1].excluded == [3]
    assert 3 not in r.out_of_control_points
    assert r.limits.points_used == 24
    # límites iguales a los de los 24 subgrupos sin el 4
    clean = phase_one("xbar_r", [row for k, row in enumerate(data) if k != 3])
    assert r.charts[0].ucl[0] == pytest.approx(clean.charts[0].ucl[0])


def test_i_mr_excluded_point_marks_adjacent_moving_ranges():
    x = list(MORTGAGE)
    x[5] = 400.0
    r = phase_one("i_mr", x, excluded=[(5, "Error de digitación")])
    assert r.charts[0].excluded == [5]
    assert r.charts[1].excluded == [5, 6]       # MR_5 = |x5-x4| y MR_6 = |x6-x5|
    assert r.in_control
    to_response(r)


def test_all_but_two_excluded_variables():
    r = phase_one("xbar_r", PISTON, excluded=[(k, "prueba") for k in range(2, 25)])
    assert r.limits.points_used == 2
    assert len(r.charts[0].values) == 25
    assert any("20 a 25" in w for w in r.warnings)


def test_sigma_zero_phase_one():
    r = phase_one("xbar_r", [[5.0, 5.0]] * 6, rules=list(RULE_IDS))
    assert r.in_control
    assert r.limits.params["sigma"] == 0.0
    assert any("dispersión estimada es 0" in w for w in r.warnings)
    assert set(r.charts[0].rules_skipped) == set(ZONE_RULES)
    to_response(r)


def test_phase_two_variables_never_recalculates_and_rebuilds_with_new_n():
    p1 = phase_one("xbar_r", PISTON)
    mu, sigma = p1.limits.params["mu"], p1.limits.params["sigma"]
    rng = np.random.default_rng(3)
    new = (74.02 + 0.01 * rng.standard_normal((10, 3))).tolist()  # proceso desplazado, n = 3
    p2 = phase_two("xbar_r", new, p1.limits)
    xbar, r = p2.charts
    assert xbar.center[0] == pytest.approx(mu)                     # no se recalcula
    assert xbar.ucl[0] == pytest.approx(mu + 3 * sigma / math.sqrt(3))
    assert r.center[0] == pytest.approx(K.d2(3) * sigma)
    assert r.ucl[0] == pytest.approx((K.d2(3) + 3 * K.d3(3)) * sigma)
    assert any("n = 3" in w for w in p2.warnings)
    assert p2.limits.subgroup_size == 5                            # los congelados no cambian
    assert not p2.in_control


def test_phase_two_accepts_contract_frozen_limits():
    p1 = phase_one("i_mr", MORTGAGE)
    contract = FrozenLimits.model_validate(p1.limits.to_contract())
    for frozen in (contract, contract.model_dump()):
        p2 = phase_two("i_mr", [300, 305, 299, 340], frozen, rules=["WE1"])
        assert p2.out_of_control_points == [3]
        assert p2.charts[0].ucl[0] == pytest.approx(p1.charts[0].ucl[0])
        to_response(p2)


def test_phase_two_errors():
    p1 = phase_one("xbar_s", PISTON)
    with pytest.raises(SPCInputError) as exc:
        phase_two("xbar_s", PISTON, None)
    assert exc.value.code == "missing_limits"
    with pytest.raises(SPCInputError):
        phase_two("xbar_r", PISTON, p1.limits)                     # otro tipo de gráfico
    bad = FrozenParameters("xbar_s", 5, "sbar_c4", {"mu": 1.0}, 25)
    with pytest.raises(SPCInputError):
        phase_two("xbar_s", PISTON, bad)                            # falta sigma


@pytest.mark.parametrize("width", [0, 0.0, -1.0, float("nan"), float("inf"), None, "tres", True])
def test_frozen_limit_width_invalid_is_rejected(width):
    # H16: un L de 0 (o no válido) en límites congelados ya no se cambia por 3 en silencio.
    p1 = phase_one("xbar_r", PISTON)
    data = {**p1.limits.to_contract(), "limit_width": width}
    with pytest.raises(SPCInputError):
        FrozenParameters.from_mapping(data)
    with pytest.raises(SPCInputError):
        phase_two("xbar_r", PISTON, data)


def test_frozen_limit_width_missing_defaults_to_three():
    p1 = phase_one("xbar_r", PISTON, limit_width=2.5)
    data = p1.limits.to_contract()
    assert FrozenParameters.from_mapping(data).limit_width == 2.5
    data.pop("limit_width")
    assert FrozenParameters.from_mapping(data).limit_width == 3.0   # valor por defecto del contrato


# --- validación de exclusiones -----------------------------------------------------


@pytest.mark.parametrize("excluded", [
    [{"index": 3, "cause": ""}],
    [{"index": 3}],
    [(3, "a"), (3, "b")],
    [(30, "fuera de rango")],
    [(-1, "negativo")],
])
def test_invalid_exclusions(excluded):
    with pytest.raises(SPCInputError):
        phase_one("xbar_r", PISTON, excluded=excluded)


def test_labels_are_used():
    labels = [f"L{k}" for k in range(30)]
    r = attributes_phase_one("p", OJ_D, OJ_N, labels=labels)
    assert r.charts[0].labels == labels
    assert "L14" in r.charts[0].violations[0].description
    with pytest.raises(SPCInputError):
        attributes_phase_one("p", OJ_D, OJ_N, labels=labels[:3])


def test_attributes_phase_two_function():
    p1 = attributes_phase_one("u", PC_C, PC_N)
    p2 = attributes_phase_two("u", [30, 5], [5, 5], p1.limits)
    assert p2.out_of_control_points == [0]


def test_no_nan_anywhere():
    for res in (phase_one("p", [0, 0, 0], [10, 10, 10]),
                phase_one("i_mr", [1.0, 1.0, 1.0]),
                phase_one("u", [0, 0], [0.5, 1.5])):
        for panel in res.charts:
            for seq in (panel.values, panel.center, panel.ucl, panel.lcl):
                assert all(math.isfinite(v) for v in seq)
        to_response(res)
