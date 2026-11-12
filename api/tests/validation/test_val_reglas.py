"""Validación independiente de rules.py.

1. Comparación masiva contra `reglas_ingenuas` (bucles explícitos, sin cumsum ni
   corridas vectorizadas) en series aleatorias de varios tipos, con y sin
   exclusiones.
2. Para cada regla, una serie que la activa justo en el último punto y otra que
   se queda a un punto.
3. Límites asimétricos, puntos excluidos y comparaciones estrictas.
4. ARL en control de WE4/N2/N3/N4 en paneles asimétricos (duda 1): cadena de
   Markov propia para R y simulación con la lógica del software para MR.
"""

import numpy as np
import pytest
from scipy import integrate, stats

from app.spc import constants as K
from app.spc.rules import RULE_IDS, evaluate_rules, first_signal

from .independiente import arl_orden_iid, arl_racha, reglas_ingenuas


def _sw(x, rule, **kw):
    kw.setdefault("sigma", 1.0)
    return [v.index for v in evaluate_rules(x, 0.0, rules=[rule], **kw).violations]


def test_software_igual_a_implementacion_ingenua():
    rng = np.random.default_rng(20261111)
    for rep in range(300):
        m = int(rng.integers(5, 70))
        kind = rep % 4
        if kind == 0:
            x = rng.normal(rng.uniform(-1.5, 1.5), rng.uniform(0.5, 2.0), m)
        elif kind == 1:
            x = np.cumsum(rng.normal(0, 0.4, m))
        elif kind == 2:
            x = 1.5 * (-1.0) ** np.arange(m) + rng.normal(0, 0.05, m)
        else:
            x = rng.normal(0, 0.3, m)
        excl = sorted(set(rng.integers(0, m, int(rng.integers(0, 4))).tolist())) if rep % 2 else []
        for r in RULE_IDS:
            assert _sw(x, r, excluded=excl) == reglas_ingenuas(x, 0.0, 1.0, r, excluded=excl), (rep, r)


# (regla, serie que se activa justo en el último punto, serie a un punto)
JUSTO = {
    "WE1": ([0, 0, 3.01], [0, 0, 2.99]),
    "WE2": ([0, 2.1, 0.5, 2.2], [0, 2.1, 0.5, 0.5, 2.2]),
    "WE3": ([0, 1.1, 1.2, 0.3, 1.3, 1.4], [0, 1.1, 1.2, 0.3, 0.2, 1.3, 1.4]),
    "WE4": ([-0.5] + [0.2] * 8, [-0.5] + [0.2] * 7),
    "N2": ([-0.5] + [0.2] * 9, [-0.5] + [0.2] * 8),
    "N3": ([0.5, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6], [0.5, 0.1, 0.2, 0.3, 0.4, 0.5]),
    "N4": ([0.1 * ((-1) ** i) for i in range(14)], [0.1 * ((-1) ** i) for i in range(13)]),
    "N7": ([2.0] + [0.5 * (-1) ** i for i in range(15)], [2.0] + [0.5 * (-1) ** i for i in range(14)]),
    "N8": ([0.2] + [1.5 * (-1) ** i for i in range(8)], [0.2] + [1.5 * (-1) ** i for i in range(7)]),
}
JUSTO["N1"], JUSTO["N5"], JUSTO["N6"] = JUSTO["WE1"], JUSTO["WE2"], JUSTO["WE3"]


@pytest.mark.parametrize("rule", sorted(JUSTO))
def test_regla_se_activa_justo_y_no_a_un_punto(rule):
    yes, no = JUSTO[rule]
    assert _sw(yes, rule)[:1] == [len(yes) - 1]
    assert _sw(no, rule) == []


def test_comparaciones_estrictas_en_los_bordes():
    assert _sw([0, 3.0, -3.0], "WE1") == []
    assert _sw([0, 2.0, 2.0], "WE2") == []
    assert _sw([1.0, 1.0, 1.0, 1.0], "WE3") == []
    assert _sw([0.3] * 4 + [0.0] + [0.3] * 4, "WE4") == []          # sobre la LC corta la racha
    assert _sw([0.5] * 7 + [1.0] + [0.5] * 7, "N7") == []            # |z| = 1 no está en zona C
    assert _sw([1.0, -1.5, 1.5, -1.5, 1.5, -1.5, 1.5, -1.5], "N8") == []


def test_limites_asimetricos_y_excluidos():
    # Panel tipo R: LC 2, LCS 4.3, LCI 0 -> sin zonas; WE4 respecto de la LC
    x = [1.0] * 8
    out = evaluate_rules(x, 2.0, ucl=4.3, lcl=0.0, rules=list(RULE_IDS), symmetric=False)
    assert set(out.skipped) == {"WE2", "WE3", "N5", "N6", "N7", "N8"}
    assert [v.index for v in out.violations if v.rule == "WE4"] == [7]
    # el excluido no recibe señal y la corrida salta sobre él
    x = [0.2] * 4 + [5.0] + [0.2] * 4
    assert _sw(x, "WE1", excluded=[4]) == []
    assert _sw(x, "WE4", excluded=[4]) == [8]


def test_limites_por_punto_n_variable():
    sig = np.array([0.02, 0.03, 0.02, 0.03])
    x = 0.1 + np.array([2.5, 0.0, 2.5, 0.0]) * sig
    out = evaluate_rules(x, 0.1, ucl=0.1 + 3 * sig, lcl=0.1 - 3 * sig, sigma=sig, rules=["WE2"])
    assert [v.index for v in out.violations] == [2]
    assert reglas_ingenuas(x, 0.1, sig, "WE2") == [2]


# --------------------------------------------------------------- duda 1


def _cdf_rango(w, n):
    f = lambda x: n * stats.norm.pdf(x) * (stats.norm.cdf(x + w) - stats.norm.cdf(x)) ** (n - 1)  # noqa: E731
    return integrate.quad(f, -12, 12, epsabs=1e-12)[0]


def test_we4_en_r_tiene_mas_falsas_alarmas_que_en_un_panel_simetrico():
    """P(R > R̄) < 0.5: con n = 2 la WE4 sola da ARL0 = 173.7 en lugar de 255 (cadena propia)."""
    p_abajo = _cdf_rango(K.d2(2), 2)
    assert 1 - p_abajo == pytest.approx(0.4249, abs=5e-4)
    assert arl_racha(0.5, 0.5, 8) == pytest.approx(255.0)
    assert arl_racha(1 - p_abajo, p_abajo, 8) == pytest.approx(173.7, abs=0.1)
    # La simulación con la lógica del software coincide con la cadena
    rng = np.random.default_rng(3)
    r = np.abs(rng.standard_normal((6000, 3000)) - rng.standard_normal((6000, 3000))) * 1.0
    fs = first_signal(r, K.d2(2), ucl=K.D4(2) * K.d2(2), lcl=0.0, rules=["WE4"], symmetric=False)
    assert (fs >= 0).all()
    est = np.mean(fs + 1)
    se = np.std(fs + 1) / np.sqrt(fs.size)
    assert abs(est - 173.7) < 4 * se


def test_we4_y_n3_en_mr_por_correlacion_serial():
    """En MR la asimetría y la correlación entre MR consecutivos se suman:
    WE4 sola ≈ 96 (no 255) y N3 sola ≈ 260 (no 421.6, el valor exacto con datos
    independientes, ver `test_n3_n4_no_dependen_de_la_asimetria`). Por eso el software
    ya no aplica estas reglas al panel MR (H5, decisión de los autores)."""
    rng = np.random.default_rng(11)
    x = rng.standard_normal((6000, 3001))
    mr = np.abs(np.diff(x, axis=1))
    d2 = K.d2(2)
    fs = first_signal(mr, d2, ucl=K.D4(2) * d2, lcl=0.0, rules=["WE4"], symmetric=False)
    assert 85 < np.mean(fs[fs >= 0] + 1) < 107
    fs = first_signal(mr, d2, ucl=K.D4(2) * d2, lcl=0.0, rules=["N3"], symmetric=False)
    assert 235 < np.mean(fs[fs >= 0] + 1) < 285


def test_panel_mr_solo_reglas_de_limite():
    """H5, decisión aplicada: en el panel MR solo se evalúan WE1 y N1."""
    from app.spc import phases
    x = np.random.default_rng(2).standard_normal(40).tolist()
    r = phases.phase_one("i_mr", x, rules=list(RULE_IDS))
    i, mr = r.charts
    assert sorted(mr.rules_applied) == ["N1", "WE1"]
    assert set(mr.rules_skipped) == set(RULE_IDS) - {"WE1", "N1"}
    assert set(i.rules_applied) == set(RULE_IDS)


def test_n3_n4_no_dependen_de_la_asimetria():
    """H5, duda de los autores: N3 y N4 dependen solo del orden. Con datos i.i.d.
    continuos su ARL0 no depende de la distribución. Exacto (ecuación integral):
    N3 = 421.6 y N4 = 601.0. La simulación con la lógica del software en R con n = 2
    (asimétrico) coincide (el 437 que reportaron los autores era ruido de simulación)."""
    n3, n4 = arl_orden_iid("N3"), arl_orden_iid("N4")
    assert n3 == pytest.approx(421.6, abs=0.1) and n4 == pytest.approx(601.0, abs=0.1)
    d2 = K.d2(2)
    for rule, exact, T in (("N3", n3, 3000), ("N4", n4, 5000)):
        rng = np.random.default_rng(17)
        rl = []
        for _ in range(3):
            r = np.abs(rng.standard_normal((2000, T)) - rng.standard_normal((2000, T)))
            fs = first_signal(r, d2, ucl=K.D4(2) * d2, lcl=0.0, rules=[rule], symmetric=False)
            rl.append(np.where(fs >= 0, fs + 1, T))
        rl = np.concatenate(rl)
        assert abs(rl.mean() - exact) < 4 * rl.std() / np.sqrt(rl.size), rule


def test_we4_con_empates_en_la_linea_central():
    """Cadena propia: si la LC coincide con un conteo posible, los puntos sobre ella
    cortan la racha y WE4 da MENOS falsas alarmas que la nominal (255), no más.
    c̄ = 2: P(X > 2) = 0.3233, P(X < 2) = 0.4060 -> ARL0 = 1 924.
    p con n = 100 y p̄ = 0.01 (n·p̄ = 1) -> ARL0 = 4 508. Con c̄ = 4.25 (sin empates), 166."""
    assert arl_racha(stats.poisson.sf(2, 2), stats.poisson.cdf(1, 2), 8) == pytest.approx(1924.1, abs=0.5)
    assert arl_racha(stats.binom.sf(1, 100, 0.01), stats.binom.cdf(0, 100, 0.01), 8) == pytest.approx(4507.9, abs=0.5)
    assert arl_racha(stats.poisson.sf(4, 4.25), stats.poisson.cdf(4, 4.25), 8) == pytest.approx(166.2, abs=0.1)
    # la lógica del software (un conteo igual a la LC corta la racha) coincide con la cadena
    rng = np.random.default_rng(5)
    rl = []
    for _ in range(4):
        x = rng.poisson(2.0, (1000, 16000)).astype(float)
        fs = first_signal(x, 2.0, ucl=2 + 3 * np.sqrt(2), lcl=0.0, rules=["WE4"], symmetric=False)
        rl.append(np.where(fs >= 0, fs + 1, 16000))
    rl = np.concatenate(rl)
    assert abs(rl.mean() - 1924.1) < 4 * rl.std() / np.sqrt(rl.size)


C_ENTERO = [1] * 8 + [3, 2] * 8 + [2]          # c̄ = 50/25 = 2 exacto; WE4 en el índice 7


def test_advertencia_we4_con_linea_central_entera():
    from app.spc import phases
    r = phases.phase_one("c", C_ENTERO, rules=["WE1", "WE4"])
    assert r.limits.params["c_bar"] == pytest.approx(2.0)
    assert any(v.rule == "WE4" for v in r.charts[0].violations)
    assert not any("mayor que la nominal" in w for w in r.warnings)
