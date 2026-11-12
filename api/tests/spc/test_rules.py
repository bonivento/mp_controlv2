"""Pruebas de rules.py (Western Electric y Nelson).

Las series se construyen a mano con sigma = 1 y línea central 0, de modo que
z = x. El índice esperado de cada señal es el punto donde la regla se completa
(Montgomery, sección 5.3.6, tabla 5.1; Nelson, 1984). No se usa ningún valor
publicado: el esperado sale de la definición de la regla.
"""

import numpy as np
import pytest

from app.spc.rules import (
    ASYMMETRY_SENSITIVE_RULES,
    LIMIT_RULES,
    NELSON,
    NON_ZONE_RULES,
    RULE_IDS,
    RULES,
    WESTERN_ELECTRIC,
    ZONE_RULES,
    ControlLimits,
    applicable_rules,
    asymmetry_warning,
    evaluate_limits,
    evaluate_rules,
    first_signal,
    signal_matrix,
)


def hits(values, rule, **kw):
    kw.setdefault("sigma", 1.0)
    out = evaluate_rules(values, 0.0, rules=[rule], **kw)
    return [v.index for v in out.violations if v.rule == rule]


def zigzag(n, base=0.5, amp=0.2):
    """n puntos que alternan subiendo y bajando, todos del mismo lado (> 0)."""
    return [base + (amp if i % 2 else 0.0) for i in range(n)]


# --- catálogo -----------------------------------------------------------------


def test_catalog_and_zone_classification():
    assert set(RULES) == set(RULE_IDS)
    assert WESTERN_ELECTRIC == ("WE1", "WE2", "WE3", "WE4")
    assert NELSON == tuple(f"N{i}" for i in range(1, 9))
    assert set(NON_ZONE_RULES) == {"WE1", "WE4", "N1", "N2", "N3", "N4"}
    assert set(ZONE_RULES) == {"WE2", "WE3", "N5", "N6", "N7", "N8"}


def test_unknown_rule_rejected():
    with pytest.raises(ValueError):
        evaluate_rules([0, 1, 2], 0, sigma=1, rules=["N9"])


# --- regla 1 ------------------------------------------------------------------


@pytest.mark.parametrize("rule", ["WE1", "N1"])
def test_rule1_beyond_limits(rule):
    x = [0, 3.01, 0, -3.2, 3.0, -3.0]
    assert hits(x, rule) == [1, 3]  # exactamente sobre el límite no es señal


def test_rule1_description_in_spanish_uses_labels():
    out = evaluate_rules([0, 5, 0], 0, sigma=1, rules=["WE1"], labels=["a", "lote-7", "c"])
    (v,) = out.violations
    assert v.index == 1
    assert "lote-7" in v.description and "por encima del límite superior" in v.description


# --- WE2 / N5: 2 de 3 más allá de 2 sigma -------------------------------------


@pytest.mark.parametrize("rule", ["WE2", "N5"])
def test_two_of_three(rule):
    assert hits([0, 2.5, 0, 2.5, 0], rule) == [3]
    assert hits([2.5, 0, 0, 2.5], rule) == []          # 2 en 4: fuera de ventana
    assert hits([2.5, -2.5, 0], rule) == []            # lados opuestos
    assert hits([0, -2.1, -2.2], rule) == [2]          # se completa en el segundo
    assert hits([0, 2.0, 2.0], rule) == []             # exactamente 2 sigma no cuenta


# --- WE3 / N6: 4 de 5 más allá de 1 sigma -------------------------------------


@pytest.mark.parametrize("rule", ["WE3", "N6"])
def test_four_of_five(rule):
    x = [0, 1.5, 1.5, 0, 1.5, 1.5, 0]
    assert hits(x, rule) == [5]
    assert hits([1.5, 1.5, 0, 0, 1.5, 1.5], rule) == []
    assert hits([-1.2, -1.3, -1.4, -1.5], rule) == [3]


# --- WE4 / N2: corridas de un lado --------------------------------------------


def test_we4_eight_on_one_side():
    x = [0.1] * 8
    assert hits(x, "WE4") == [7]
    assert hits(x[:7], "WE4") == []
    assert hits([0.1] * 4 + [0.0] + [0.1] * 4, "WE4") == []   # punto en la LC rompe
    assert hits([-0.1] * 10, "WE4") == [7, 8, 9]              # se marca en cada punto adicional


def test_n2_nine_on_one_side():
    assert hits([0.3] * 8, "N2") == []
    assert hits([0.3] * 9, "N2") == [8]


# --- N3: tendencia de 6 puntos ------------------------------------------------


def test_n3_trend_six_points():
    up = [0, 0.1, 0.2, 0.3, 0.4, 0.5]
    assert hits(up, "N3") == [5]
    assert hits(up[:5], "N3") == []
    assert hits([0.5, 0.4, 0.3, 0.2, 0.1, 0.0, -0.1], "N3") == [5, 6]
    assert hits([0, 0.1, 0.2, 0.2, 0.3, 0.4, 0.5], "N3") == []   # empate rompe


# --- N4: 14 puntos alternando arriba y abajo ----------------------------------


def test_n4_alternating_up_down_not_sides():
    x = zigzag(14)  # todos por encima de la LC: alternar lados sería imposible
    assert all(v > 0 for v in x)
    assert hits(x, "N4") == [13]
    assert hits(zigzag(13), "N4") == []


def test_n4_tie_breaks_alternation():
    x = zigzag(14)
    x[7] = x[6]  # diferencia nula
    assert hits(x, "N4") == []


def test_n4_alternating_sides_monotone_pattern_is_not_needed():
    """Un patrón que alterna lados pero no dirección no puede existir; en cambio,
    uno que alterna lados de a dos puntos (+,+,-,-) no alterna dirección y no
    debe disparar N4 aunque cambie de lado constantemente."""
    x = [0.5, 0.6, -0.5, -0.6] * 4
    assert hits(x, "N4") == []


# --- N7 y N8 ------------------------------------------------------------------


def test_n7_fifteen_in_zone_c():
    x = [0.5 * (-1) ** i for i in range(15)]
    assert hits(x, "N7") == [14]
    assert hits(x[:14], "N7") == []
    x2 = list(x)
    x2[7] = 1.2
    assert hits(x2, "N7") == []


def test_n8_eight_outside_zone_c_both_sides():
    x = [1.5 * (-1) ** i for i in range(8)]
    assert hits(x, "N8") == [7]
    assert hits(x, "N6") == []  # no hay 4 de 5 del mismo lado
    x[3] = 0.5
    assert hits(x, "N8") == []


def test_n8_description_distinguishes_mixture_from_shift():
    # H11: a ambos lados es mezcla; todos del mismo lado es un desplazamiento.
    mixed = evaluate_rules([1.5 * (-1) ** i for i in range(8)], 0.0, sigma=1.0, rules=["N8"])
    (v,) = mixed.violations
    assert "ambos lados" in v.description and "mezcla de poblaciones" in v.description
    for sign, side in ((1, "por encima"), (-1, "por debajo")):
        out = evaluate_rules([sign * 1.5] * 8, 0.0, sigma=1.0, rules=["N8"])
        (v,) = out.violations
        assert v.index == 7
        assert side in v.description and "desplazamiento" in v.description
        assert "mezcla" not in v.description
    # la ventana de 8 decide: 2 por debajo seguidos de 8 por encima se describe como desplazamiento
    out = evaluate_rules([-1.5, -1.5] + [1.5] * 8, 0.0, sigma=1.0, rules=["N8"])
    assert [v.index for v in out.violations] == [7, 8, 9]
    assert ["mezcla" in v.description for v in out.violations] == [True, True, False]


# --- simetría y zonas ----------------------------------------------------------


def test_asymmetric_limits_skip_zone_rules():
    # Gráfico R típico: LC 2, LCS 4.3, LCI 0 (truncado)
    out = evaluate_rules([2, 2.5, 4.5, 3.9, 3.9], 2.0, ucl=4.3, lcl=0.0, rules=RULE_IDS)
    assert set(out.applied) == set(NON_ZONE_RULES)
    assert set(out.skipped) == set(ZONE_RULES)
    assert all("no se aplica" in msg for msg in out.skipped.values())
    assert [v.index for v in out.violations if v.rule == "WE1"] == [2]


def test_asymmetric_panel_warns_once_about_side_runs():
    # H5: en un panel asimétrico WE4 y N2 se aplican, con advertencia de falsas alarmas.
    out = evaluate_rules([1.0] * 9, 2.0, ucl=4.3, lcl=0.0, rules=["WE1", "WE4", "N2"])
    assert out.applied == ["WE1", "WE4", "N2"]
    assert [v.rule for v in out.violations] == ["WE4", "WE4", "N2"]
    (w,) = out.warnings
    assert w.startswith("Las reglas WE4 y N2 se aplicaron")
    assert "falsas alarmas es mayor que la nominal" in w and "indicio a confirmar" in w


def test_asymmetric_warning_text_by_rule_set():
    assert asymmetry_warning(["WE1"]) is None
    assert asymmetry_warning([]) is None
    one = asymmetry_warning(["WE1", "WE4"])
    assert one.startswith("La regla WE4 se aplicó") and "esta regla es un indicio" in one
    # N3 y N4 dependen solo del orden: no se afirma que aumenten las falsas alarmas.
    order = asymmetry_warning(["N3", "N4"])
    assert order.startswith("El estadístico graficado es asimétrico; las reglas N3 y N4 dependen solo del orden")
    assert "mayor que la nominal" not in order
    both = asymmetry_warning(["WE4", "N3"])
    assert "WE4 se aplicó" in both and "La regla N3 depende solo del orden" in both
    # H25: cada oración empieza en mayúscula
    assert all(sent.strip()[0].isupper() for sent in both.split(". ") if sent.strip())
    assert ". La regla N3 depende solo del orden" in both


def test_asymmetric_warning_text_for_counts_does_not_claim_higher():
    # H19: con conteos la tasa es distinta de la nominal (mucho menor si la LC es un conteo posible).
    w = asymmetry_warning(["WE1", "WE4", "N2"], discrete=True)
    assert w.startswith("Las reglas WE4 y N2 se aplicaron aunque el gráfico es de conteos con límites asimétricos")
    assert "mayor que la nominal" not in w.replace("mayor si la línea central no es un valor posible", "")
    assert "distinta de la nominal" in w and "posiblemente mucho menor" in w and "pérdida de sensibilidad" in w
    assert "cortan la racha" in w and "indicio a confirmar" in w
    order = asymmetry_warning(["N3"], discrete=True)
    assert order.startswith("El gráfico es de conteos con límites asimétricos; la regla N3 depende solo del orden")


def test_fmt_sin_notacion_cientifica():
    from app.spc.rules import _fmt
    assert _fmt(1234567.89) == "1234568"
    assert _fmt(-2.5e7) == "-25000000"
    assert _fmt(1.23456789e-5) == "0,0000123457"
    assert _fmt(0.5) == "0,5"
    assert _fmt(12.3456789) == "12,3457"
    for v in (1e6, 3.2e9, 1e-7, 123456.7):
        assert "e" not in _fmt(v)


def test_no_asymmetry_warning_when_symmetric_or_not_requested():
    assert evaluate_rules([0.1] * 9, 0.0, sigma=1.0, rules=["WE4", "N2", "N3"]).warnings == []
    assert evaluate_rules([1.0] * 9, 2.0, ucl=4.3, lcl=0.0, rules=["WE1", "WE2"]).warnings == []


def test_serially_correlated_only_limit_rules():
    # Panel MR: solo WE1 y N1; el resto se omite con el motivo de la correlación serial.
    x = [0.5] * 9 + [5.0]
    out = evaluate_rules(x, 1.128, ucl=3.686, lcl=0.0, rules=RULE_IDS, serially_correlated=True)
    assert out.applied == list(LIMIT_RULES)
    assert set(out.skipped) == set(RULE_IDS) - set(LIMIT_RULES)
    assert all("correlacionados" in m for m in out.skipped.values())
    assert [(v.rule, v.index) for v in out.violations] == [("WE1", 9), ("N1", 9)]
    assert out.warnings == []                                   # no quedan reglas de racha
    # sin la marca, WE4 y N2 sí señalarían en la misma serie
    plain = evaluate_rules(x, 1.128, ucl=3.686, lcl=0.0, rules=["WE4", "N2"])
    assert [v.index for v in plain.violations] == [7, 8, 8]


def test_motivo_de_zonas_habla_de_la_distribucion_del_estadistico():
    # H25: el motivo no afirma que los límites sean asimétricos (en R con n >= 7 son simétricos).
    out = evaluate_rules([1.0] * 5, 1.0, ucl=2.0, lcl=0.0, rules=["WE2"], symmetric=False)
    msg = out.skipped["WE2"]
    assert msg.startswith("WE2 no se aplica: la distribución del estadístico graficado es asimétrica")
    assert "los límites no son simétricos" not in msg


def test_applicable_rules_default_unchanged():
    # design.py depende de esta firma y de este comportamiento por defecto.
    applied, skipped = applicable_rules(["WE1", "WE2", "WE4", "N3"], False, "motivo")
    assert applied == ["WE1", "WE4", "N3"] and skipped == {"WE2": "WE2 no se aplica: motivo."}
    applied, skipped = applicable_rules(["WE1", "WE4"], True, serially_correlated=True)
    assert applied == ["WE1"] and list(skipped) == ["WE4"]
    assert set(ASYMMETRY_SENSITIVE_RULES) == {"WE4", "N2", "N3", "N4"}


def test_descriptions_use_decimal_comma():
    out = evaluate_rules([0.0, 3.25], 0.0, sigma=1.0, rules=["WE1"])
    (v,) = out.violations
    assert "(3,25)" in v.description and "(3)" in v.description and "3.25" not in v.description


def test_symmetric_false_forced_even_if_limits_look_symmetric():
    # R con n >= 7 tiene D3 > 0 y límites numéricamente simétricos, pero R es asimétrico.
    out = evaluate_rules([1, 1, 1], 1.0, ucl=1.9, lcl=0.1, rules=["WE2", "WE1"], symmetric=False)
    assert out.applied == ["WE1"] and "WE2" in out.skipped


def test_symmetric_inferred_from_limits():
    out = evaluate_rules([0, 2.5, 2.5], 0.0, ucl=3.0, lcl=-3.0, rules=["WE2"])
    assert out.applied == ["WE2"]
    assert [v.index for v in out.violations] == [2]


def test_per_point_zones_with_variable_limits():
    # p con n variable: mismo valor, distinto sigma por punto.
    center = 0.10
    sigma = np.array([0.03, 0.03, 0.01, 0.01, 0.03])
    x = np.array([0.10, 0.10, 0.125, 0.125, 0.10])  # z = 0, 0, 2.5, 2.5, 0
    out = evaluate_rules(x, center, ucl=center + 3 * sigma, lcl=center - 3 * sigma, rules=["WE2"])
    assert [v.index for v in out.violations] == [3]
    # con el sigma grande en todos, 0.125 queda en z = 0.83 y no hay señal
    out2 = evaluate_rules(x, center, sigma=0.03, rules=["WE2"])
    assert out2.violations == []


def test_zero_sigma_skips_zones_and_no_false_alarm():
    out = evaluate_rules([5.0] * 10, 5.0, sigma=0.0, rules=RULE_IDS)
    assert set(out.skipped) == set(ZONE_RULES)
    assert out.violations == []
    out = evaluate_rules([5.0] * 9 + [5.1], 5.0, sigma=0.0, rules=["WE1"])
    assert [v.index for v in out.violations] == [9]


def test_controllimits_shortcut():
    lim = ControlLimits(center=np.array(0.0), ucl=np.array(3.0), lcl=np.array(-3.0),
                        sigma=np.array(1.0), symmetric=True)
    out = evaluate_limits([0, 2.5, 2.5, 3.5], lim, ["WE1", "WE2"])
    assert [(v.rule, v.index) for v in out.violations] == [("WE2", 2), ("WE1", 3), ("WE2", 3)]


# --- puntos excluidos ----------------------------------------------------------


def test_excluded_points_do_not_take_part_in_runs():
    x = [0.2] * 4 + [-1.0] + [0.2] * 4  # el punto 4 rompería la corrida
    assert hits(x, "WE4") == []
    assert hits(x, "WE4", excluded=[4]) == [8]


def test_excluded_point_never_flagged():
    x = [0, 0, 10.0, 0]
    assert hits(x, "WE1", excluded=[2]) == []


def test_excluded_inside_k_of_m_window():
    # sin el excluido, 2.5, [0 excluido], 2.5 quedan consecutivos
    assert hits([0, 2.5, 0, 0, 2.5], "WE2") == []
    assert hits([0, 2.5, 0, 0, 2.5], "WE2", excluded=[2, 3]) == [4]


def test_all_excluded_returns_nothing():
    out = evaluate_rules([1, 2, 3], 0, sigma=1, rules=["WE1"], excluded=[0, 1, 2])
    assert out.violations == []


def test_indices_mapping_for_moving_range():
    out = evaluate_rules([0.1, 9.0], 0.5, ucl=3.0, lcl=0.0, rules=["WE1"],
                         symmetric=False, indices=[1, 2])
    assert [v.index for v in out.violations] == [2]


# --- versión vectorizada -------------------------------------------------------


def test_signal_matrix_matches_scalar_evaluation():
    rng = np.random.default_rng(7)
    x = rng.normal(0.3, 1.0, size=(30, 60))
    m = signal_matrix(x, 0.0, sigma=1.0, rules=RULE_IDS)
    for row in range(x.shape[0]):
        out = evaluate_rules(x[row], 0.0, sigma=1.0, rules=RULE_IDS)
        assert sorted(set(np.flatnonzero(m[row]).tolist())) == out.indices


def test_first_signal():
    x = np.array([[0, 0, 4, 0], [0, 0, 0, 0], [-4, 0, 0, 0]], dtype=float)
    assert first_signal(x, 0.0, sigma=1.0, rules=["WE1"]).tolist() == [2, -1, 0]


def test_signal_matrix_refuses_inapplicable_rules():
    with pytest.raises(ValueError):
        signal_matrix(np.zeros((2, 5)), 1.0, ucl=2.0, lcl=0.0, rules=["WE2"], symmetric=False)


def test_rule1_false_alarm_rate():
    """P(|Z| > 3) = 0.0027 (Montgomery, sección 5.3.2). Con 2·10^6 puntos el
    error estándar de la proporción es ≈ 3.7e-5."""
    rng = np.random.default_rng(2024)
    x = rng.standard_normal((200, 10_000))
    rate = signal_matrix(x, 0.0, sigma=1.0, rules=["WE1"]).mean()
    assert rate == pytest.approx(0.0026998, abs=4 * 3.7e-5)
