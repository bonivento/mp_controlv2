"""Validación de los textos de interpretation.py: que no afirmen más de lo que
los datos permiten. Cada `xfail(strict=True)` es un hallazgo con su caso mínimo.
"""

import re

import numpy as np
import pytest

from app.spc import phases
from app.spc.assumptions import analyze_assumptions
from app.spc.capability import analyze_capability
from app.spc.interpretation import interpret_chart_result
from app.spc.sampling import design_single_plan
from tests.spc.test_attributes import OJ_D, OJ_N
from tests.spc.test_phases import OJ_PHASE2


def _txt(it):
    return " ".join([it.summary, *it.findings, *it.warnings])


def test_fase_uno_no_declara_en_control_al_excluido():
    r = phases.phase_one("c", [5, 6, 4, 30, 5, 6, 5, 4, 6, 5], excluded=[(3, "lote defectuoso")])
    it = interpret_chart_result(r, rules=["WE1"])
    assert "los 10 subgrupos están en control" not in it.summary


def test_concordancia_un_excluido():
    r = phases.phase_one("c", [5, 6, 4, 30, 5, 6, 5, 4, 6, 5], excluded=[(3, "lote defectuoso")])
    assert "1 subgrupos" not in _txt(interpret_chart_result(r))


def test_fase_dos_no_repite_exclusiones():
    rev = phases.phase_one("p", OJ_D, OJ_N, excluded=[(14, "cartón"), (22, "operario")])
    labels = [f"F2-{k}" for k in range(24)]
    p2 = phases.phase_two("p", OJ_PHASE2, rev.limits, sizes=[50] * 24, labels=labels)
    text = _txt(interpret_chart_result(p2))
    assert "Siguen graficados" not in text and "F2-14" not in text


def test_supuestos_no_afirma_cumplimiento_por_no_rechazar():
    r = analyze_assumptions([10.1, 9.8, 10.3, 10.0, 9.7, 10.2, 9.9, 10.4])
    assert r.is_normal and r.is_independent
    assert "se cumplen" not in r.interpretation.summary


def test_capacidad_sin_estabilidad_no_da_veredicto_firme():
    sg = np.random.default_rng(2).normal(10, 0.2, (25, 5)).tolist()
    it = analyze_capability(sg, lsl=9.0, usl=11.0).interpretation
    assert "veredicto de capacidad adecuado" not in it.summary or "estab" in it.summary


def test_capacidad_congelada_advierte_intervalo():
    rng = np.random.default_rng(2)
    lim = {"chart_type": "xbar_r", "params": {"mu": 10.0, "sigma": 0.2}}
    r = analyze_capability(rng.normal(10, 0.2, (100, 5)).tolist(), lsl=9.0, usl=11.0, limits=lim,
                           is_stable=True, is_normal=True)
    assert any("aproximad" in w for w in r.interpretation.warnings)


def test_muestreo_no_inventa_lectura_de_nomograma():
    r = design_single_plan(0.005, 0.03, 0.05, 0.10)
    assert not any("suele proponer" in f for f in r.interpretation.findings)


def test_n8_mismo_lado_no_es_mezcla():
    from app.spc.rules import evaluate_rules
    out = evaluate_rules([1.5] * 8, 0.0, sigma=1.0, rules=["N8"])
    assert out.violations and "mezcla" not in out.violations[0].description


def test_concordancia_pruebas_que_rechazan():
    x = np.random.default_rng(3).exponential(size=60)
    assert "Anderson-Darling rechaza)" not in analyze_assumptions(x).interpretation.summary


def test_razon_de_sigmas_no_afirma_causa_sin_prueba():
    for seed in range(200):
        x = np.random.default_rng(seed).normal(0, 1, 30)
        r = analyze_capability([[v] for v in x], lsl=-4.0, usl=4.0, is_stable=True, is_normal=True)
        if r.sigma_overall / r.sigma_within > 1.10:
            break
    assert not any("Hay variación entre subgrupos" in f for f in r.interpretation.findings)


def _fase1():
    import csv
    from pathlib import Path
    path = Path(__file__).resolve().parents[3] / "data" / "ejemplos" / "sintetico_fase1.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    return [[float(r[f"x{k}"]) for k in range(1, 6)] for r in rows]


def test_fase1_sintetico_cuenta_los_retenidos():
    r = phases.phase_one("xbar_r", _fase1(), excluded=[(11, "boquilla obstruida")])
    assert r.limits.points_used == 24
    assert "los 25 subgrupos están en control" not in interpret_chart_result(r, rules=["WE1"]).summary


def test_ljung_box_fase1_depurada_calculo_correcto():
    """Caso de otro agente: el p = 0.0245 es correcto (Q recalculada por FFT)."""
    from .independiente import ljung_box_propio
    x = np.array([g for i, g in enumerate(_fase1()) if i != 11]).ravel()
    q, p = ljung_box_propio(x, 20)
    r = analyze_assumptions(x)
    assert r.independence[0].statistic == pytest.approx(q) and r.independence[0].p_value == pytest.approx(p)
    assert p == pytest.approx(0.0245, abs=1e-4)
    assert r.autocorrelation.significant_lags == [6] and r.autocorrelation.values[5] < 0


def test_ljung_box_fase1_depurada_texto_no_afirma_demasiado():
    x = np.array([g for i, g in enumerate(_fase1()) if i != 11]).ravel()
    it = analyze_assumptions(x).interpretation
    assert "están autocorrelacionadas" not in it.summary
    assert not any("AR(1)" in w for w in it.warnings)


def _sin_secciones(t):
    """Quita las referencias de sección ("sección 6.2"), que sí llevan punto."""
    return re.sub(r"secci[oó]n \d+(\.\d+)+", "", t)


def test_numeros_con_coma_decimal():
    """H12, corregido. La versión anterior de esta prueba (`test_decimales_con_punto_documentado`)
    comprobaba que hubiera un "." en el resumen, algo que el punto final de cualquier frase
    cumple: no medía nada. Ahora se busca un dígito, punto y dígito en todos los textos de
    los módulos (también descripciones de rules.py y advertencias de phases.py)."""
    from app.spc.design import compute_arl
    from app.spc.sampling import evaluate_single_plan
    rng = np.random.default_rng(1)
    textos = [analyze_capability(rng.normal(10, 0.2, (25, 5)).tolist(), lsl=9.0, usl=11.0, target=10.05).interpretation,
              analyze_assumptions(rng.exponential(size=60)).interpretation,
              compute_arl("xbar", n=5, limit_width=2.5, shifts=[0.5, 1.5], sampling_interval=0.25).interpretation,
              compute_arl("p", n=80, p0=0.05).interpretation,
              evaluate_single_plan(89, 2, lot_size=1000, aql=0.01, ltpd=0.06, alpha=0.05, beta=0.10).interpretation]
    for ct, data, sizes in (("xbar_r", (rng.normal(10, 0.2, (12, 5)) + np.r_[np.zeros(11), 1.0][:, None]).tolist(), None),
                            ("p", [3, 5, 2, 14, 4, 3, 6, 2], [80, 100, 90, 85, 100, 120, 95, 100]),
                            ("i_mr", rng.normal(5.5, 0.3, 30).tolist(), None)):
        r = phases.phase_one(ct, data, sizes, rules=["WE1", "WE2", "WE4", "N3"])
        textos.append(interpret_chart_result(r, rules=["WE1", "WE2", "WE4", "N3"]))
        textos += [type("T", (), {"summary": v.description, "findings": [], "warnings": []})
                   for p in r.charts for v in p.violations]
    for it in textos:
        t = _sin_secciones(_txt(it))
        assert not re.search(r"\d\.\d", t), re.search(r".{40}\d\.\d.{20}", t)


# ---------------------------------------------------------------- segunda pasada


def _r_con_tendencia():
    sg = np.random.default_rng(5).normal(10, 1, (25, 5))
    for k, w in enumerate([0.6, 0.9, 1.2, 1.5, 1.8, 2.1]):
        sg[10 + k] = 10 + np.linspace(-w, w, 5)
    return sg.tolist()


def test_n3_en_panel_r_sin_contradiccion():
    r = phases.phase_one("xbar_r", _r_con_tendencia(), rules=["WE1", "N3"])
    assert [v.rule for v in r.charts[1].violations] == ["N3"]
    it = interpret_chart_result(r, rules=["WE1", "N3"])
    assert any("no aumenta su tasa de falsas alarmas" in w for w in it.warnings)
    assert not any("(N3) dan falsas alarmas más a menudo" in f for f in it.findings)


def test_n4_en_u_sintetico_sin_contradiccion():
    import csv
    from pathlib import Path
    path = Path(__file__).resolve().parents[3] / "data" / "ejemplos" / "sintetico_u_n_variable.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    rules = ["WE1", "N4"]
    r = phases.phase_one("u", [int(x["defectos"]) for x in rows], [float(x["unidades_inspeccion"]) for x in rows], rules=rules)
    it = interpret_chart_result(r, rules=rules)
    assert any(v.rule == "N4" for v in r.charts[0].violations)
    assert not any("(N4) dan falsas alarmas más a menudo" in f for f in it.findings)


@pytest.mark.parametrize("estable", [False, None])
def test_capacidad_no_estable_no_afirma_con_confianza(estable):
    sg = np.random.default_rng(2).normal(10, 0.2, (25, 5)).tolist()
    it = analyze_capability(sg, lsl=8.5, usl=11.5, is_stable=estable, is_normal=True).interpretation
    assert "no se puede declarar" in it.summary or "condicional" in it.summary
    assert not any("de confianza Cpk supera" in f for f in it.findings)


def test_forma_no_se_afirma_dentro_del_error_de_muestreo():
    x = [10.1, 9.8, 10.3, 10.0, 9.7, 10.2, 9.9, 10.4]          # G2 = -1.2, EE(G2) ≈ 1.48 con n = 8
    it = analyze_assumptions(x).interpretation
    assert not any("colas más livianas que la normal" in f for f in it.findings)


def test_probabilidad_de_rezago_fuera_por_azar():
    x = np.array([g for i, g in enumerate(_fase1()) if i != 11]).ravel()
    it = analyze_assumptions(x).interpretation
    assert "0,64" not in it.summary


def test_mr_no_habla_de_subgrupos():
    import csv
    from pathlib import Path
    path = Path(__file__).resolve().parents[3] / "data" / "ejemplos" / "sintetico_i_mr.csv"
    v = [float(r["valor"]) for r in csv.DictReader(path.open(encoding="utf-8"))]
    it = interpret_chart_result(phases.phase_one("i_mr", v), rules=["WE1"])
    assert not any("rangos móviles indican que cambió la variabilidad dentro de los subgrupos" in f for f in it.findings)


def test_redaccion_de_el():
    sg = np.random.default_rng(4).normal(10, 0.3, (25, 5)).tolist()
    it = analyze_capability(sg, lsl=9.0, usl=11.0, is_stable=True, is_normal=True).interpretation
    assert any("está por debajo de" in f for f in it.findings)
    assert " de el " not in _txt(it)


def test_redaccion_mayuscula_advertencia_asimetria():
    r = phases.phase_one("xbar_r", _fase1(), rules=["WE1", "WE4", "N3"])
    assert not any(". las reglas" in w or ". la regla" in w for w in r.warnings)


def test_redaccion_lci_constante():
    r = phases.phase_one("p", [3, 5, 2, 4, 3, 6], [80, 100, 90, 85, 100, 120])
    assert "LCI entre 0 y 0" not in _txt(interpret_chart_result(r))


def test_motivo_de_zonas_en_s_con_limites_simetricos():
    import csv
    from pathlib import Path
    path = Path(__file__).resolve().parents[3] / "data" / "ejemplos" / "sintetico_xbar_s_n10.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    sg = [[float(r[f"x{k}"]) for k in range(1, 11)] for r in rows]
    s = phases.phase_one("xbar_s", sg, rules=["WE1", "WE2"]).charts[1]
    assert s.ucl[0] - s.center[0] == pytest.approx(s.center[0] - s.lcl[0], rel=1e-9)
    assert "los límites no son simétricos" not in s.rules_skipped["WE2"]
