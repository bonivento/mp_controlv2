"""Interpretación automática de resultados (conclusiones preliminares).

Cada función recibe un resultado ya calculado y devuelve un `Interpretation`
con tres partes, todas en español y con los números del caso:

- `summary`: una o dos frases con la conclusión principal.
- `findings`: qué pasó, dónde y qué implica para el proceso, uno por elemento.
- `warnings`: supuestos incumplidos y limitaciones del análisis.

Este módulo no importa los módulos de cálculo: lee los resultados por sus
atributos (o claves, si llegan como diccionarios), así que puede usarse con
las dataclasses de `spc` o con los modelos Pydantic del contrato.

Criterios de referencia (Montgomery, *Introduction to Statistical Quality
Control*):
- Capacidad (cap. 8): Cpk < 1 inadecuado; 1 a 1.33 marginal; 1.33 a 1.67
  adecuado; >= 1.67 excelente. Montgomery recomienda 1.33 para procesos
  existentes y 1.50 para procesos nuevos (tabla de valores mínimos de Cp).
- Diseño de gráficos (cap. 6 y 7): ARL0 de 370.4 con límites de 3 sigma.
- Muestreo de aceptación (cap. 15): riesgo del productor α en AQL y del
  consumidor β en LTPD.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional, Sequence


@dataclass
class Interpretation:
    summary: str
    findings: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# Formato de números
# --------------------------------------------------------------------------


def fmt(x: Optional[float], digits: int = 4) -> str:
    """Número con `digits` cifras significativas; 'no disponible' si es None."""
    if x is None:
        return "no disponible"
    x = float(x)
    if not math.isfinite(x):
        return "no disponible"
    if x == 0:
        return "0"
    if abs(x) >= 10 ** digits:
        return f"{x:,.0f}".replace(",", " ")
    s = f"{x:.{digits}g}"
    if "e" in s:
        s = f"{x:.{digits + 2}f}".rstrip("0").rstrip(".")
    return s


def fmt_p(p: Optional[float]) -> str:
    """Valor p: cuatro decimales o '< 0.0001'."""
    if p is None:
        return "no disponible"
    if p < 0.0001:
        return "< 0.0001"
    return f"{p:.4f}"


def fmt_pct(x: Optional[float], digits: int = 2) -> str:
    if x is None:
        return "no disponible"
    return f"{100 * x:.{digits}f} %"


def fmt_ppm(fraction: Optional[float]) -> str:
    if fraction is None:
        return "no disponible"
    ppm = fraction * 1e6
    if 0 < ppm < 0.001:
        return "< 0.001 PPM"
    if ppm >= 100:
        return f"{ppm:,.0f} PPM".replace(",", " ")
    return f"{ppm:.3g} PPM"


def _get(obj: Any, key: str, default: Any = None) -> Any:
    """Lee un atributo o una clave (dataclass, modelo Pydantic o dict)."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _join(items: Iterable[str]) -> str:
    items = list(items)
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " y " + items[-1]


# ==========================================================================
# Módulo 4. Supuestos
# ==========================================================================


def interpret_assumptions(result: Any, alpha: float = 0.05) -> Interpretation:
    """Interpreta normalidad e independencia (`AssumptionsResult`)."""
    d = _get(result, "descriptive")
    n = int(_get(d, "count"))
    normality = _get(result, "normality")
    independence = _get(result, "independence")
    is_normal = bool(_get(result, "is_normal"))
    is_independent = bool(_get(result, "is_independent"))
    ac = _get(result, "autocorrelation")
    findings: list[str] = []
    warnings: list[str] = []

    findings.append(
        f"Se analizaron {n} observaciones en orden temporal: media {fmt(_get(d, 'mean'))}, "
        f"desviación estándar {fmt(_get(d, 'std'))}, mínimo {fmt(_get(d, 'min'))} y máximo "
        f"{fmt(_get(d, 'max'))}."
    )
    for t in normality:
        findings.append(f"{_get(t, 'name')}: {_get(t, 'conclusion')}")

    skew = _get(d, "skewness")
    kurt = _get(d, "kurtosis")
    shape = []
    if skew is not None and abs(skew) >= 0.5:
        side = "valores altos" if skew > 0 else "valores bajos"
        shape.append(
            f"la asimetría es {fmt(skew, 3)}, con una cola más larga hacia {side}"
        )
    if kurt is not None and abs(kurt) >= 1:
        if kurt > 0:
            shape.append(
                f"el exceso de curtosis es {fmt(kurt, 3)}: colas más pesadas que la normal, "
                "con más valores extremos de los esperados"
            )
        else:
            shape.append(
                f"el exceso de curtosis es {fmt(kurt, 3)}: colas más livianas que la normal, "
                "lo que puede indicar mezcla de dos fuentes o datos truncados (por ejemplo, "
                "piezas seleccionadas antes de medir)"
            )
    if shape:
        findings.append("Forma de la distribución: " + "; ".join(shape) + ".")

    qq = _get(result, "qq") or []
    if len(qq) >= 3:
        th = [float(_get(p, "theoretical")) for p in qq]
        ob = [float(_get(p, "observed")) for p in qq]
        r = _corr(th, ob)
        if r is not None:
            findings.append(
                f"En el gráfico Q-Q la correlación entre cuantiles teóricos y observados es "
                f"{fmt(r, 4)}; cuanto más cerca de 1, más se alinean los puntos sobre la recta normal."
            )

    lags = list(_get(ac, "lags") or [])
    vals = list(_get(ac, "values") or [])
    band = float(_get(ac, "band"))
    sig = list(_get(ac, "significant_lags") or [])
    if sig:
        detail = _join(
            f"r{k} = {fmt(vals[lags.index(k)], 3)}" for k in sig[:6]
        )
        extra = f" (y {len(sig) - 6} más)" if len(sig) > 6 else ""
        findings.append(
            f"La autocorrelación supera la banda ±{fmt(band, 3)} en {len(sig)} de {len(lags)} "
            f"rezagos: {detail}{extra}."
        )
        if 1 in sig and vals[0] > 0:
            findings.append(
                f"La autocorrelación de rezago 1 es positiva ({fmt(vals[0], 3)}): cada observación "
                "se parece a la anterior. Es típico de procesos continuos o de un muestreo más "
                "frecuente que la dinámica del proceso."
            )
        elif 1 in sig and vals[0] < 0:
            findings.append(
                f"La autocorrelación de rezago 1 es negativa ({fmt(vals[0], 3)}): a un valor alto "
                "le sigue uno bajo, patrón típico de ajustes del operador después de cada medición."
            )
    else:
        findings.append(
            f"Ningún rezago entre 1 y {len(lags)} supera la banda ±{fmt(band, 3)} de la función de "
            "autocorrelación."
        )
    for t in independence:
        findings.append(f"{_get(t, 'name')}: {_get(t, 'conclusion')}")

    # Advertencias
    rejected_norm = [_get(t, "name") for t in normality if _get(t, "reject")]
    if not is_normal:
        warnings.append(
            f"Se rechaza la normalidad ({_join(rejected_norm)}). Los índices de capacidad y la "
            "fracción no conforme esperada suponen normalidad y no serán confiables; conviene "
            "transformar los datos (por ejemplo, Box-Cox), ajustar otra distribución o apoyarse en "
            "la fracción no conforme observada. El gráfico de individuales es el más sensible a "
            "este problema; el de X-barra con n >= 4 lo es menos por el teorema central del límite."
        )
        if len(rejected_norm) < len(normality):
            warnings.append(
                "Las pruebas de normalidad no coinciden: Anderson-Darling da más peso a las colas "
                "y Shapiro-Wilk a la forma general. Revise el histograma y el gráfico Q-Q antes de decidir."
            )
    if not is_independent:
        warnings.append(
            "Las observaciones no son independientes. Con autocorrelación positiva, la sigma "
            "estimada con rangos móviles o dentro de subgrupos subestima la variabilidad y los "
            "límites de Shewhart producen falsas alarmas frecuentes. Montgomery (cap. 10) "
            "recomienda modelar la serie (por ejemplo, un AR(1)) y graficar los residuos, o "
            "espaciar más las muestras."
        )
    elif sig:
        expected_false = alpha * len(lags)
        warnings.append(
            f"Algunos rezagos salen de la banda pero las pruebas globales no rechazan la "
            f"independencia. Con {len(lags)} rezagos y α = {fmt(alpha, 3)} se esperan unos "
            f"{fmt(expected_false, 2)} rezagos fuera de banda solo por azar."
        )
    if n < 20:
        warnings.append(
            f"Con solo {n} observaciones las pruebas tienen poca potencia: no rechazar H0 no "
            "demuestra que el supuesto se cumpla."
        )
    if n > 5000:
        warnings.append(
            "Con más de 5000 observaciones las pruebas rechazan ante desvíos mínimos sin "
            "importancia práctica; juzgue la normalidad también por el gráfico Q-Q."
        )

    if is_normal and is_independent:
        summary = (
            f"Las {n} observaciones son compatibles con una distribución normal y con "
            "independencia: se cumplen los supuestos de los gráficos de Shewhart y de los índices "
            "de capacidad basados en la normal."
        )
    elif not is_normal and is_independent:
        summary = (
            f"Las {n} observaciones son independientes pero no normales ({_join(rejected_norm)} "
            "rechaza): los gráficos de control pueden usarse con cautela, pero los índices de "
            "capacidad basados en la normal no son confiables."
        )
    elif is_normal and not is_independent:
        summary = (
            f"Las {n} observaciones son compatibles con la normal pero están autocorrelacionadas: "
            "los límites de Shewhart darán falsas alarmas y conviene modelar la dependencia antes "
            "de controlar el proceso."
        )
    else:
        summary = (
            f"Las {n} observaciones no cumplen ni normalidad ni independencia: antes de construir "
            "gráficos de control o estimar capacidad hay que tratar la autocorrelación y la forma "
            "de la distribución."
        )
    return Interpretation(summary=summary, findings=findings, warnings=warnings)


def _corr(a: Sequence[float], b: Sequence[float]) -> Optional[float]:
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    sab = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    saa = sum((x - ma) ** 2 for x in a)
    sbb = sum((y - mb) ** 2 for y in b)
    if saa <= 0 or sbb <= 0:
        return None
    return sab / math.sqrt(saa * sbb)


# ==========================================================================
# Módulo 7. Muestreo de aceptación
# ==========================================================================

_DIST_NAMES = {
    "binomial": "binomial (curva OC tipo B)",
    "poisson": "Poisson (aproximación de la binomial)",
    "hypergeometric": "hipergeométrica (curva OC tipo A, lote finito)",
}


def _risk_finding(kind: str, level: float, pa: float, actual: float, target: Optional[float]) -> str:
    if kind == "alpha":
        head = (
            f"Riesgo del productor: un lote con AQL = {fmt_pct(level)} defectuoso se acepta con "
            f"probabilidad {fmt(pa, 4)}, es decir α real = {fmt(actual, 4)}"
        )
        if target is None:
            return head + "."
        ok = actual <= target
        return head + (
            f" (objetivo ≤ {fmt(target, 3)}): cumple."
            if ok
            else f" (objetivo ≤ {fmt(target, 3)}): no cumple; se rechazarían más lotes buenos de lo pactado."
        )
    head = (
        f"Riesgo del consumidor: un lote con LTPD = {fmt_pct(level)} defectuoso se acepta con "
        f"probabilidad β real = {fmt(actual, 4)}"
    )
    if target is None:
        return head + "."
    ok = actual <= target
    return head + (
        f" (objetivo ≤ {fmt(target, 3)}): cumple."
        if ok
        else f" (objetivo ≤ {fmt(target, 3)}): no cumple; pasarían más lotes malos de lo pactado."
    )


def interpret_single_plan(
    result: Any,
    aql: Optional[float] = None,
    ltpd: Optional[float] = None,
    alpha: Optional[float] = None,
    beta: Optional[float] = None,
    lot_size: Optional[int] = None,
    search: Any = None,
    reference: Optional[dict] = None,
    pa_at: Any = None,
) -> Interpretation:
    """Interpreta un plan simple (`SinglePlanResult`).

    `search` (`DesignSearch`) explica por qué no sirve un c menor; `reference`
    ({n, c, alpha_actual, beta_actual}) compara con otro plan, por ejemplo el
    de un nomograma; `pa_at(p)` permite citar Pa en AQL y LTPD.
    """
    n, c = int(_get(result, "n")), int(_get(result, "c"))
    dist = _get(result, "distribution")
    a_act, b_act = _get(result, "alpha_actual"), _get(result, "beta_actual")
    aoql, aoql_at = _get(result, "aoql"), _get(result, "aoql_at")
    findings: list[str] = []
    warnings: list[str] = []

    rule = (
        f"se inspeccionan {n} unidades de cada lote y se acepta el lote si aparecen {c} o menos "
        f"defectuosas; con {c + 1} o más se rechaza"
    )
    if search is not None:
        summary = (
            f"El plan de menor tamaño que cumple α ≤ {fmt(alpha, 3)} en AQL = {fmt_pct(aql)} y "
            f"β ≤ {fmt(beta, 3)} en LTPD = {fmt_pct(ltpd)} es n = {n}, c = {c}: {rule}."
        )
    else:
        summary = f"Plan simple n = {n}, c = {c}: {rule}."
        unmet = []
        if a_act is not None and alpha is not None and a_act > alpha:
            unmet.append("α")
        if b_act is not None and beta is not None and b_act > beta:
            unmet.append("β")
        if unmet:
            summary += f" El plan no cumple {_join(unmet)} objetivo."

    if a_act is not None:
        findings.append(_risk_finding("alpha", aql, 1 - a_act, a_act, alpha))
    if b_act is not None:
        findings.append(_risk_finding("beta", ltpd, b_act, b_act, beta))
    if aql is not None and ltpd is not None:
        findings.append(
            f"La razón de discriminación LTPD/AQL es {fmt(ltpd / aql, 3)}: cuanto más cerca de 1, "
            "más difícil distinguir lotes buenos de malos y más grande debe ser la muestra."
        )

    if search is not None and _get(search, "previous_c") is not None:
        pc, pn = _get(search, "previous_c"), _get(search, "previous_n")
        pal, pbe = _get(search, "previous_alpha"), _get(search, "previous_beta")
        findings.append(
            f"Con c = {pc} el menor tamaño que cumple β es n = {pn} (β = {fmt(pbe, 4)}), pero ese "
            f"plan da α = {fmt(pal, 4)} > {fmt(alpha, 3)}, y aumentar n solo empeora α. Por eso "
            f"hay que pasar a c = {c}, con el que el menor n que cumple ambos riesgos es {n}."
        )
        findings.append(
            f"Un nomograma binomial (Montgomery, cap. 15) suele proponer un plan con c = {pc} cerca "
            f"de n = {pn}: la lectura gráfica es aproximada y no garantiza el riesgo del productor. "
            "Aquí cada plan se verificó con la distribución exacta."
        )
    if reference is not None:
        rn, rc = reference["n"], reference["c"]
        ra, rb = reference.get("alpha_actual"), reference.get("beta_actual")
        parts = []
        if ra is not None:
            ok = alpha is None or ra <= alpha
            parts.append(f"α = {fmt(ra, 4)}" + ("" if ok else f" (supera {fmt(alpha, 3)})"))
        if rb is not None:
            ok = beta is None or rb <= beta
            parts.append(f"β = {fmt(rb, 4)}" + ("" if ok else f" (supera {fmt(beta, 3)})"))
        verdict = ""
        if (ra is not None and alpha is not None and ra > alpha) or (
            rb is not None and beta is not None and rb > beta
        ):
            verdict = f" No cumple los riesgos pactados; el plan n = {n}, c = {c} sí."
        findings.append(
            f"Plan de referencia n = {rn}, c = {rc}: {_join(parts) if parts else 'sin AQL ni LTPD para comparar'}.{verdict}"
        )

    aoq_text = (
        f"Con inspección rectificadora (los lotes rechazados se inspeccionan al 100 % y se "
        f"reemplazan las defectuosas), la calidad promedio de salida nunca supera AOQL = "
        f"{fmt_pct(aoql)}, valor que se alcanza cuando los lotes llegan con {fmt_pct(aoql_at)} "
        "defectuoso. Ese es el peor promedio que recibiría el cliente."
    )
    if lot_size is None:
        aoq_text += " Se calculó con AOQ ≈ Pa·p porque no se informó el tamaño de lote."
    findings.append(aoq_text)

    if lot_size is not None and pa_at is not None:
        parts = []
        for label, p in (("AQL", aql), ("LTPD", ltpd)):
            if p is None:
                continue
            ati = n + (1 - pa_at(p)) * (lot_size - n)
            parts.append(f"en {label} ({fmt_pct(p)}) se inspeccionan en promedio {fmt(ati, 4)} unidades")
        if parts:
            findings.append(
                f"Inspección total promedio por lote de N = {lot_size}: {_join(parts)}. La diferencia "
                "es el costo de inspección que generan los lotes rechazados."
            )

    findings.append(f"Las probabilidades se calcularon con la distribución {_DIST_NAMES.get(dist, dist)}.")
    if dist == "binomial" and lot_size is not None and n / lot_size > 0.10:
        warnings.append(
            f"La muestra es el {fmt_pct(n / lot_size, 1)} del lote: con fracciones mayores al 10 % "
            "la binomial sobrestima la variabilidad y conviene usar la hipergeométrica."
        )
    if dist == "poisson" and ltpd is not None and ltpd > 0.10:
        warnings.append(
            "La aproximación de Poisson es buena cuando la fracción defectuosa es pequeña; con "
            f"LTPD = {fmt_pct(ltpd)} conviene confirmar con la binomial."
        )
    if dist == "hypergeometric" and lot_size is not None:
        warnings.append(
            f"Con la hipergeométrica la fracción defectuosa se traduce en D = redondeo(p·{lot_size}) "
            "unidades defectuosas del lote, así que α y β corresponden a ese número entero."
        )
        if aql is not None and round(aql * lot_size) == 0:
            warnings.append(
                f"AQL·N = {fmt(aql * lot_size, 3)} redondea a 0 defectuosas: con un lote sin "
                "defectuosas el plan siempre acepta y α real es 0."
            )
    if a_act is not None and alpha is not None and a_act > alpha and search is None:
        warnings.append(
            f"α real {fmt(a_act, 4)} supera el objetivo {fmt(alpha, 3)}: aumente c (y n) para proteger al productor."
        )
    if b_act is not None and beta is not None and b_act > beta and search is None:
        warnings.append(
            f"β real {fmt(b_act, 4)} supera el objetivo {fmt(beta, 3)}: aumente n para proteger al consumidor."
        )
    warnings.append(
        "El plan supone lotes formados por unidades del mismo proceso y muestra aleatoria. El "
        "muestreo de aceptación no mejora la calidad: solo decide sobre lotes; la mejora viene "
        "del control estadístico del proceso."
    )
    return Interpretation(summary=summary, findings=findings, warnings=warnings)


def interpret_double_plan(
    result: Any,
    n1: int,
    c1: int,
    r1: int,
    n2: int,
    c2: int,
    lot_size: Optional[int] = None,
    aql: Optional[float] = None,
    ltpd: Optional[float] = None,
    aoql_at: Optional[float] = None,
    probabilities: Any = None,
) -> Interpretation:
    """Interpreta un plan doble (`DoublePlanResult`).

    `probabilities(p)` debe devolver (Pa^I, Pa^II, P(segunda muestra)).
    """
    a_act, b_act = _get(result, "alpha_actual"), _get(result, "beta_actual")
    aoql = _get(result, "aoql")
    findings: list[str] = []
    warnings: list[str] = []
    summary = (
        f"Plan doble n1 = {n1}, c1 = {c1}, r1 = {r1}, n2 = {n2}, c2 = {c2}: con la primera muestra "
        f"de {n1} se acepta si hay {c1} o menos defectuosas y se rechaza con {r1} o más; entre "
        f"{c1 + 1} y {r1 - 1} se toma una segunda muestra de {n2} y se acepta si el total no pasa de {c2}."
    )
    if probabilities is not None:
        for label, p in (("AQL", aql), ("LTPD", ltpd)):
            if p is None:
                continue
            pa1, pa2, p2 = probabilities(p)
            asn = n1 + n2 * p2
            findings.append(
                f"En {label} = {fmt_pct(p)}: Pa = {fmt(pa1 + pa2, 4)} ({fmt(pa1, 4)} con la primera "
                f"muestra y {fmt(pa2, 4)} con la segunda); se necesita la segunda muestra en el "
                f"{fmt_pct(p2, 1)} de los lotes y el tamaño promedio de muestra es ASN = {fmt(asn, 4)} "
                f"unidades, frente a {n1 + n2} si siempre se tomaran las dos."
            )
    if a_act is not None:
        findings.append(_risk_finding("alpha", aql, 1 - a_act, a_act, None))
    if b_act is not None:
        findings.append(_risk_finding("beta", ltpd, b_act, b_act, None))
    findings.append(
        f"Con inspección rectificadora la calidad promedio de salida no supera AOQL = {fmt_pct(aoql)}"
        + (f", máximo que ocurre con lotes de {fmt_pct(aoql_at)} defectuoso." if aoql_at is not None else ".")
    )
    if lot_size is not None and probabilities is not None:
        parts = []
        for label, p in (("AQL", aql), ("LTPD", ltpd)):
            if p is None:
                continue
            pa1, pa2, _ = probabilities(p)
            ati = n1 * pa1 + (n1 + n2) * pa2 + lot_size * (1 - pa1 - pa2)
            parts.append(f"en {label} se inspeccionan en promedio {fmt(ati, 4)} unidades")
        if parts:
            findings.append(f"Con lotes de N = {lot_size}, {_join(parts)}.")
    findings.append(
        "La ventaja del plan doble es psicológica y económica: los lotes muy buenos o muy malos se "
        "deciden con la primera muestra, y el ASN es menor que el n de un plan simple equivalente "
        "en esos extremos."
    )
    if r1 > c2 + 1:
        warnings.append(
            f"Con r1 = {r1} > c2 + 1 = {c2 + 1}, cuando la primera muestra tiene entre {c2 + 1} y "
            f"{r1 - 1} defectuosas se toma una segunda muestra que nunca puede aceptar el lote: "
            "conviene usar r1 = c2 + 1."
        )
    if lot_size is None:
        warnings.append("Sin tamaño de lote, AOQ se aproxima con Pa·p y no se calcula el ATI.")
    warnings.append(
        "El ASN supone que la segunda muestra se inspecciona completa (sin truncar al alcanzar el "
        "número de rechazo). Las probabilidades usan la binomial."
    )
    return Interpretation(summary=summary, findings=findings, warnings=warnings)


# ==========================================================================
# Módulo 6. Diseño de gráficos (ARL, ATS)
# ==========================================================================

NOMINAL_ARL0_3SIGMA = 370.4  # 1 / (2·Φ(-3)), Montgomery cap. 6

_CHART_NAMES = {
    "xbar": "X-barra",
    "individuals": "de individuales",
    "p": "p",
    "c": "c",
}


def _hours(h: float) -> str:
    """Horas con su equivalente en días cuando conviene."""
    if h >= 48:
        return f"{fmt(h, 4)} h ≈ {fmt(h / 24, 3)} días de operación continua"
    if h < 1:
        return f"{fmt(h, 3)} h ≈ {fmt(h * 60, 3)} min"
    return f"{fmt(h, 4)} h"


def _count(x: float, singular: str, plural: str, digits: int = 4) -> str:
    """Cantidad con el sustantivo en singular o plural ('1 muestra', '4.5 muestras')."""
    return f"{fmt(x, digits)} {singular if fmt(x, digits) == '1' else plural}"


def _shift_label(chart: str, level: float, center: float) -> str:
    if chart in ("xbar", "individuals"):
        return f"un desplazamiento de la media de {fmt(level, 3)}σ"
    if chart == "p":
        return f"una fracción no conforme de {fmt_pct(level)} (en control {fmt_pct(center)})"
    return f"una media de {fmt(level, 4)} no conformidades por unidad (en control {fmt(center, 4)})"


def interpret_arl(
    result: Any,
    chart: str,
    n: int,
    limit_width: float,
    sampling_interval: float,
    model: Any = None,
    count_bounds: Optional[tuple[int, int]] = None,
    rules_requested: Sequence[str] = ("WE1",),
    rules_skipped: Optional[dict] = None,
    simulation: Optional[dict] = None,
    attribute_defaults: bool = False,
) -> Interpretation:
    """Interpreta el desempeño de un gráfico (`ArlResult`)."""
    method = _get(result, "method")
    arl0 = float(_get(result, "arl0"))
    ats0 = float(_get(result, "ats0"))
    alpha = _get(result, "alpha")
    load = float(_get(result, "sampling_load"))
    rows = list(_get(result, "rows") or [])
    h = sampling_interval
    center = float(_get(model, "center", 0.0)) if model is not None else 0.0
    name = _CHART_NAMES.get(chart, chart)
    findings: list[str] = []
    warnings: list[str] = []

    design = f"gráfico {name} con L = {fmt(limit_width, 3)}"
    if chart in ("xbar", "p"):
        design += f", n = {n}"
    design += f" y una muestra cada {_hours(h)}"

    focus = None
    if rows:
        if chart in ("xbar", "individuals"):
            focus = next((r for r in rows if abs(float(_get(r, "shift")) - 1.0) < 1e-12), rows[0])
        else:
            focus = rows[0]
    summary = (
        f"Con un {design}, el proceso en control da una falsa alarma cada {fmt(arl0, 4)} muestras "
        f"en promedio (ATS0 = {_hours(ats0)})"
    )
    if focus is not None:
        summary += (
            f" y {_shift_label(chart, float(_get(focus, 'shift')), center)} se detecta en "
            f"{_count(float(_get(focus, 'arl1')), 'muestra', 'muestras')} ({_hours(float(_get(focus, 'ats1')))})."
        )
    else:
        summary += "."
    if method == "simulation" and simulation:
        summary += " Valores estimados por simulación con reglas suplementarias."

    if alpha is not None:
        findings.append(
            f"Probabilidad de falsa alarma por muestra: α = {fmt(alpha, 4)} "
            f"({fmt_pct(alpha, 3)} de las muestras con el proceso en control), por eso ARL0 = 1/α = {fmt(arl0, 4)}."
        )

    # Gráficos por atributos: ARL0 real frente al nominal
    if chart in ("p", "c") and model is not None and count_bounds is not None:
        a, b = count_bounds
        unit = "unidades no conformes en la muestra" if chart == "p" else "no conformidades"
        findings.append(
            f"Límites: LCS = {fmt(_get(model, 'ucl'), 4)} y LCI = {fmt(_get(model, 'lcl'), 4)}. Como el "
            f"conteo es entero, el gráfico no da señal mientras haya entre {a} y {b} {unit}."
        )
        if alpha is not None and abs(limit_width - 3.0) < 1e-12:
            findings.append(
                f"El ARL0 real es {fmt(arl0, 4)}, no el nominal {NOMINAL_ARL0_3SIGMA} de los límites "
                "de 3 sigma con la normal. El conteo es discreto y asimétrico: la probabilidad de "
                f"falsa alarma queda en {fmt(alpha, 4)} en lugar de 0.0027"
                + (
                    ", y con el LCI truncado en 0 toda esa probabilidad está en la cola superior."
                    if _get(model, "lcl_truncated")
                    else "."
                )
                + (
                    " Habrá más falsas alarmas de las que sugiere la regla de 3 sigma."
                    if arl0 < NOMINAL_ARL0_3SIGMA
                    else " Habrá menos falsas alarmas de las que sugiere la regla de 3 sigma."
                )
            )
        if _get(model, "lcl_truncated"):
            findings.append(
                "El límite inferior es 0, así que el gráfico no puede señalar mejoras (disminuciones "
                "de la fracción o de la media de defectos); las filas con valores menores al de "
                "control muestran ARL1 muy grandes por esa razón."
            )

    for r in rows:
        lv = float(_get(r, "shift"))
        arl1 = float(_get(r, "arl1"))
        beta = _get(r, "beta")
        text = (
            f"Ante {_shift_label(chart, lv, center)}: ARL1 = {_count(arl1, 'muestra', 'muestras')}"
        )
        se = _get(r, "std_error")
        if se is not None:
            text += f" (error estándar {fmt(se, 3)})"
        text += (
            f", ATS1 = {_hours(float(_get(r, 'ats1')))} y "
            f"{_count(float(_get(r, 'units_to_detect')), 'unidad inspeccionada', 'unidades inspeccionadas')} "
            "hasta la señal"
        )
        if beta is not None:
            p3 = 1 - float(beta) ** 3
            text += (
                f"; β = {fmt(beta, 4)}, así que la probabilidad de detectarlo en la primera muestra "
                f"es {fmt(1 - float(beta), 4)} y en las tres primeras {fmt(p3, 4)}"
            )
        findings.append(text + ".")

    slow = [r for r in rows if float(_get(r, "arl1")) > 10 and chart in ("xbar", "individuals")
            and float(_get(r, "shift")) > 0]
    if slow:
        r = slow[0]
        findings.append(
            f"El gráfico es lento para desplazamientos pequeños: con {fmt(_get(r, 'shift'), 3)}σ "
            f"tarda {fmt(_get(r, 'arl1'), 4)} muestras. Para detectarlos antes conviene aumentar n, "
            "muestrear con más frecuencia o usar un gráfico CUSUM o EWMA (Montgomery, cap. 9)."
        )
    findings.append(
        f"Carga muestral: {fmt(load, 4)} unidades inspeccionadas por hora. Es el costo que se compara "
        "con la rapidez de detección al elegir n y h."
    )

    if method == "simulation" and simulation:
        applied = simulation.get("applied", [])
        findings.append(
            f"Reglas evaluadas: {_join(applied)}. Con reglas suplementarias la longitud de corrida "
            f"no es geométrica, así que se estimó por Monte Carlo: {simulation['runs']} corridas por "
            f"estado, cada una hasta {simulation['max_length']} muestras, semilla {simulation['seed']}. "
            f"ARL0 = {fmt(arl0, 4)} con error estándar {fmt(simulation['arl0_std_error'], 3)}."
        )
        sh0 = simulation.get("shewhart_arl0")
        if sh0 is not None:
            ratio = sh0 / arl0 if arl0 > 0 else None
            text = (
                f"Solo con la regla de un punto fuera de límites el ARL0 sería {fmt(sh0, 4)}: las "
                f"reglas suplementarias multiplican las falsas alarmas por {fmt(ratio, 3)}"
            )
            sh1 = simulation.get("shewhart_arl1") or []
            if focus is not None and sh1:
                idx = rows.index(focus)
                if idx < len(sh1) and sh1[idx] is not None:
                    text += (
                        f", a cambio de detectar {_shift_label(chart, float(_get(focus, 'shift')), center)} "
                        f"en {fmt(_get(focus, 'arl1'), 4)} muestras en lugar de {fmt(sh1[idx], 4)}"
                    )
            findings.append(text + ".")
        warnings.append(
            "La curva OC corresponde a la regla de un punto fuera de límites; con reglas "
            "suplementarias la probabilidad de no detectar depende de la historia y no se resume "
            "en un β por muestra. La curva ARL une los valores simulados."
        )
        used = simulation.get("runs_used") or []
        if used and min(used) < simulation["runs"]:
            warnings.append(
                f"Para no exceder el tiempo de cómputo, algunos estados se simularon con menos "
                f"corridas que las pedidas (mínimo {min(used)} de {simulation['runs']}); su error "
                "estándar es mayor."
            )
        censored = simulation.get("censored") or []
        if any(censored):
            total = sum(censored)
            warnings.append(
                f"{total} corridas simuladas no dieron señal antes del límite de longitud o del "
                "presupuesto de cómputo; su longitud se contó hasta ese punto, así que los ARL "
                "afectados están subestimados (son cotas inferiores)."
            )
    if rules_skipped:
        warnings.append(
            "Reglas no aplicadas porque requieren zonas simétricas: "
            + " ".join(str(v) for v in rules_skipped.values())
            + " El ARL informado corresponde a las reglas que el gráfico sí aplica."
        )
    if attribute_defaults:
        warnings.append(
            "No se enviaron estados fuera de control; se evaluaron 1.5, 2, 2.5 y 3 veces el valor en control."
        )
    warnings.append(
        "Los ARL suponen parámetros del proceso conocidos. Si μ y σ (o p, c) se estimaron con "
        "pocos subgrupos en Fase I, el ARL0 real puede ser bastante menor que el calculado."
    )
    if chart in ("xbar", "individuals"):
        warnings.append(
            "Las fórmulas suponen observaciones normales e independientes; con autocorrelación o "
            "colas pesadas las falsas alarmas son más frecuentes, en especial en el gráfico de individuales."
        )
    return Interpretation(summary=summary, findings=findings, warnings=warnings)


def interpret_compare(result: Any) -> Interpretation:
    """Interpreta la tabla comparativa de diseños X-barra (`CompareResult`)."""
    shift = float(_get(result, "shift"))
    rows = list(_get(result, "rows") or [])
    findings: list[str] = []
    warnings: list[str] = []
    if not rows:
        return Interpretation(summary="No hay diseños para comparar.")

    def label(r: Any) -> str:
        return (
            f"n = {_get(r, 'n')}, L = {fmt(_get(r, 'limit_width'), 3)}, h = {fmt(_get(r, 'sampling_interval'), 3)} h"
        )

    fastest = min(rows, key=lambda r: float(_get(r, "ats1")))
    cheapest = min(rows, key=lambda r: float(_get(r, "sampling_load")))
    summary = (
        f"Para detectar un desplazamiento de {fmt(shift, 3)}σ, el diseño más rápido es {label(fastest)}: "
        f"ATS1 = {_hours(float(_get(fastest, 'ats1')))} con una carga de "
        f"{fmt(_get(fastest, 'sampling_load'), 4)} unidades por hora y una falsa alarma cada "
        f"{_hours(float(_get(fastest, 'ats0')))}."
    )
    for r in rows:
        findings.append(
            f"{label(r)}: ARL0 = {fmt(_get(r, 'arl0'), 4)} (falsa alarma cada {_hours(float(_get(r, 'ats0')))}), "
            f"ARL1 = {fmt(_get(r, 'arl1'), 4)} (ATS1 = {_hours(float(_get(r, 'ats1')))}), carga "
            f"{fmt(_get(r, 'sampling_load'), 4)} unidades/h."
        )
    if cheapest is not fastest:
        findings.append(
            f"El diseño de menor carga es {label(cheapest)} ({fmt(_get(cheapest, 'sampling_load'), 4)} "
            f"unidades/h), pero tarda {_hours(float(_get(cheapest, 'ats1')))} en detectar; elegir entre "
            "ambos es un balance entre costo de inspección y costo de producir fuera de control."
        )
    # Mismo esfuerzo de muestreo, distinto reparto
    by_load: dict[float, list[Any]] = {}
    for r in rows:
        by_load.setdefault(round(float(_get(r, "sampling_load")), 9), []).append(r)
    for load, group in by_load.items():
        if len(group) < 2:
            continue
        best = min(group, key=lambda r: float(_get(r, "ats1")))
        worst = max(group, key=lambda r: float(_get(r, "ats1")))
        if best is worst:
            continue
        findings.append(
            f"Con la misma carga de {fmt(load, 4)} unidades/h, {label(best)} detecta en "
            f"{_hours(float(_get(best, 'ats1')))} y {label(worst)} en {_hours(float(_get(worst, 'ats1')))}: "
            "con el mismo esfuerzo conviene el reparto de la primera."
        )
    widths = sorted({float(_get(r, "limit_width")) for r in rows})
    if len(widths) > 1:
        findings.append(
            f"Al ensanchar los límites de L = {fmt(widths[0], 3)} a L = {fmt(widths[-1], 3)} se reducen "
            "las falsas alarmas (sube ARL0) pero se tarda más en detectar (sube ARL1)."
        )
    low_arl0 = [r for r in rows if float(_get(r, "arl0")) < 200]
    if low_arl0:
        warnings.append(
            f"{len(low_arl0)} diseño(s) tienen ARL0 menor que 200: las falsas alarmas frecuentes "
            "desgastan la confianza del personal en el gráfico."
        )
    warnings.append(
        "Cálculos exactos para la regla de un punto fuera de límites, con μ y σ conocidos y datos "
        "normales e independientes."
    )
    return Interpretation(summary=summary, findings=findings, warnings=warnings)


# ==========================================================================
# Módulo 5. Capacidad
# ==========================================================================

VERDICT_ES = {
    "inadequate": "inadecuado (Cpk < 1)",
    "marginal": "marginal (1 <= Cpk < 1.33)",
    "adequate": "adecuado (1.33 <= Cpk < 1.67)",
    "excellent": "excelente (Cpk >= 1.67)",
}

_SIGMA_METHOD_ES = {
    "rbar_d2": "R̄/d2",
    "sbar_c4": "S̄/c4",
    "mrbar_d2": "MR̄/d2",
    "frozen_limits": "los parámetros congelados de Fase I",
}


def _iv(index: Any) -> tuple[Optional[float], Optional[float], Optional[float]]:
    return _get(index, "value"), _get(index, "lower"), _get(index, "upper")


def interpret_capability(
    result: Any,
    lsl: Optional[float] = None,
    usl: Optional[float] = None,
    target: Optional[float] = None,
    confidence: float = 0.95,
    is_stable: Optional[bool] = None,
    is_normal: Optional[bool] = None,
    subgroup_count: Optional[int] = None,
) -> Interpretation:
    """Interpreta un análisis de capacidad (`CapabilityResult`)."""
    n = int(_get(result, "n"))
    mean = float(_get(result, "mean"))
    sw = float(_get(result, "sigma_within"))
    so = float(_get(result, "sigma_overall"))
    method = _get(result, "sigma_method")
    verdict = _get(result, "verdict")
    cp, cp_lo, cp_hi = _iv(_get(result, "cp"))
    cpk, cpk_lo, cpk_hi = _iv(_get(result, "cpk"))
    cpl = _get(_get(result, "cpl"), "value")
    cpu = _get(_get(result, "cpu"), "value")
    pp = _get(_get(result, "pp"), "value")
    ppk, ppk_lo, ppk_hi = _iv(_get(result, "ppk"))
    cpm = _get(_get(result, "cpm"), "value")
    ew = _get(result, "expected_within")
    eo = _get(result, "expected_overall")
    ob = _get(result, "observed")
    conf = fmt_pct(confidence, 0)
    findings: list[str] = []
    warnings: list[str] = []

    if lsl is not None and usl is not None:
        specs = f"especificaciones [{fmt(lsl)}, {fmt(usl)}]"
    elif lsl is not None:
        specs = f"límite inferior de especificación {fmt(lsl)}"
    else:
        specs = f"límite superior de especificación {fmt(usl)}"

    unreliable = is_stable is False or is_normal is False
    summary = (
        f"Con {specs}, Cpk = {fmt(cpk, 3)} (IC {conf}: {fmt(cpk_lo, 3)} a {fmt(cpk_hi, 3)}): "
        f"veredicto de capacidad {VERDICT_ES.get(verdict, verdict)}. Con la variación de corto plazo se "
        f"espera {fmt_ppm(_get(ew, 'total'))} fuera de especificación."
    )
    if unreliable:
        reasons = []
        if is_stable is False:
            reasons.append("el proceso no está en control estadístico")
        if is_normal is False:
            reasons.append("los datos no son normales")
        summary += f" Estos índices no son confiables porque {_join(reasons)}."

    findings.append(
        f"Se usaron {n} observaciones"
        + (f" en {subgroup_count} subgrupos" if subgroup_count and subgroup_count != n else "")
        + f": media {fmt(mean)}, sigma de corto plazo {fmt(sw)} (estimada con "
        f"{_SIGMA_METHOD_ES.get(method, method)}) y sigma de largo plazo {fmt(so)} (desviación "
        "muestral de todos los datos)."
    )

    if cp is not None:
        used = 100 / cp if cp > 0 else None
        findings.append(
            f"Cp = {fmt(cp, 3)} (IC {conf}: {fmt(cp_lo, 3)} a {fmt(cp_hi, 3)}): la tolerancia "
            f"{fmt(usl - lsl)} equivale a {fmt(cp, 3)} veces la dispersión natural 6σ = {fmt(6 * sw)}; "
            f"el proceso ocupa el {fmt(used, 3)} % del intervalo de especificación."
        )
        mid = (lsl + usl) / 2
        if cpk is not None and cp > 0 and (cp - cpk) > 0.10 * cp:
            side = "superior" if cpu is not None and cpl is not None and cpu < cpl else "inferior"
            findings.append(
                f"El proceso está descentrado: la media {fmt(mean)} está a {fmt(abs(mean - mid))} del "
                f"centro de especificaciones {fmt(mid)}, más cerca del límite {side}. Cpk "
                f"({fmt(cpk, 3)}) es menor que Cp ({fmt(cp, 3)}); centrar el proceso subiría Cpk hasta "
                f"Cp sin reducir la variación."
            )
        else:
            findings.append(
                f"El proceso está prácticamente centrado (media {fmt(mean)}, centro {fmt(mid)}): Cpk "
                f"≈ Cp, así que mejorar la capacidad exige reducir la variación."
            )
    else:
        which = "Cpl" if lsl is not None else "Cpu"
        findings.append(
            f"Con una sola especificación Cp y Pp no aplican; la capacidad se mide con {which} = "
            f"{fmt(cpk, 3)}, la distancia de la media al límite en unidades de 3σ."
        )

    if cpk is not None and cpk < 0:
        warnings.append(
            f"Cpk es negativo ({fmt(cpk, 3)}): la media del proceso está fuera de la especificación. "
            "Más de la mitad de la producción queda fuera; la acción urgente es reubicar la media."
        )

    if cpk_lo is not None and cpk is not None:
        if cpk >= 1.33 > cpk_lo:
            findings.append(
                f"Aunque la estimación puntual de Cpk ({fmt(cpk, 3)}) supera 1.33, el límite inferior "
                f"del intervalo ({fmt(cpk_lo, 3)}) no lo hace: con {n} datos no se puede afirmar con "
                f"{conf} de confianza que el proceso cumpla el mínimo de 1.33."
            )
        elif cpk_lo >= 1.33:
            findings.append(
                f"Con {conf} de confianza Cpk es al menos {fmt(cpk_lo, 3)}, por encima del mínimo "
                "recomendado de 1.33 para procesos existentes."
            )
        elif cpk_hi is not None and cpk_hi < 1:
            findings.append(
                f"Incluso el límite superior del intervalo de Cpk ({fmt(cpk_hi, 3)}) es menor que 1: "
                "la falta de capacidad no se explica por el error de muestreo."
            )

    if pp is not None or ppk is not None:
        ratio = so / sw
        if ratio > 1.10:
            findings.append(
                f"La sigma de largo plazo es {fmt(ratio, 3)} veces la de corto plazo, así que Ppk = "
                f"{fmt(ppk, 3)} queda por debajo de Cpk = {fmt(cpk, 3)}. Hay variación entre subgrupos "
                "(desplazamientos o derivas de la media en el tiempo): eliminar esas causas acercaría "
                "el desempeño real a la capacidad potencial."
            )
        elif ratio < 0.90:
            findings.append(
                f"La sigma de largo plazo es menor que la de corto plazo (razón {fmt(ratio, 3)}), algo "
                "poco habitual: puede indicar subgrupos mal formados (mezcla de fuentes dentro del "
                "subgrupo) o un estimador de corto plazo inflado."
            )
        else:
            findings.append(
                f"Las sigmas de corto ({fmt(sw)}) y largo plazo ({fmt(so)}) son similares: Ppk = "
                f"{fmt(ppk, 3)} y Cpk = {fmt(cpk, 3)} cuentan la misma historia, señal de un proceso "
                "sin grandes desplazamientos entre subgrupos."
            )

    if cpm is not None and target is not None:
        findings.append(
            f"Cpm = {fmt(cpm, 3)} con objetivo T = {fmt(target)}: penaliza la distancia de la media "
            f"al objetivo ({fmt(abs(mean - target))})."
            + (
                " Cpm es claramente menor que Ppk, así que la media se aleja del valor nominal "
                "aunque esté dentro de especificaciones."
                if ppk is not None and cpm < 0.9 * ppk
                else ""
            )
        )

    def nc_text(nc: Any) -> str:
        parts = []
        if _get(nc, "below_lsl") is not None:
            parts.append(f"{fmt_ppm(_get(nc, 'below_lsl'))} bajo LSL")
        if _get(nc, "above_usl") is not None:
            parts.append(f"{fmt_ppm(_get(nc, 'above_usl'))} sobre USL")
        return f"{fmt_ppm(_get(nc, 'total'))} ({_join(parts)})"

    n_out = int(round(float(_get(ob, "total")) * n))
    findings.append(
        f"Fracción no conforme esperada con el modelo normal: {nc_text(ew)} con sigma de corto plazo "
        f"y {nc_text(eo)} con sigma de largo plazo. Observada: {n_out} de {n} datos, "
        f"{fmt_pct(_get(ob, 'total'))}."
    )
    if n_out == 0 and float(_get(eo, "total")) * n < 1:
        findings.append(
            f"No se observó ninguna unidad fuera de especificación, coherente con lo esperado: con "
            f"{n} datos solo cabría esperar ver alguna si la fracción no conforme fuera del orden de "
            f"1/{n} ({fmt_pct(1 / n)}) o mayor, así que la fracción observada no sirve para "
            "confirmar niveles de PPM bajos."
        )
    elif float(_get(eo, "total")) > 0 and n >= 30:
        exp_count = float(_get(eo, "total")) * n
        if n_out > 2 * exp_count + 3:
            warnings.append(
                f"Se observaron {n_out} datos fuera de especificación frente a {fmt(exp_count, 3)} "
                "esperados con la normal: las colas reales son más pesadas que las del modelo y las "
                "PPM esperadas subestiman el problema."
            )

    if is_stable is False:
        warnings.append(
            "El proceso no está en control estadístico: Cp y Cpk suponen un proceso estable y "
            "predecible, así que no describen lo que el proceso producirá. Pp y Ppk solo resumen el "
            "desempeño de estos datos. Primero hay que identificar y eliminar las causas asignables "
            "y repetir el estudio (Montgomery, cap. 8)."
        )
    elif is_stable is None:
        warnings.append(
            "No se informó si el proceso está en control estadístico. Los índices solo son válidos "
            "para un proceso estable: verifíquelo con un gráfico de control (Fase I) antes de interpretarlos."
        )
    if is_normal is False:
        warnings.append(
            "Los datos no siguen una distribución normal: la relación entre los índices y la "
            "fracción no conforme (PPM esperadas) deja de valer y los intervalos de confianza no son "
            "exactos. Use la fracción observada, transforme los datos o estime la capacidad con la "
            "distribución que mejor se ajuste."
        )
    elif is_normal is None:
        warnings.append(
            "No se informó el resultado de las pruebas de normalidad; las PPM esperadas y los "
            "intervalos suponen datos normales (verifíquelo en el módulo de supuestos)."
        )
    if n < 50:
        warnings.append(
            f"Con {n} observaciones los intervalos de confianza son anchos; para conclusiones firmes "
            "se recomiendan estudios de capacidad con 100 datos o más."
        )
    if method != "frozen_limits":
        warnings.append(
            "Los intervalos de Cp y de Cpk suponen que sigma se estimó con la desviación muestral; "
            f"con {_SIGMA_METHOD_ES.get(method, method)} son aproximados."
        )
    return Interpretation(summary=summary, findings=findings, warnings=warnings)


# ==========================================================================
# Módulos 2 y 3. Gráficos de control (Fase I y Fase II)
# ==========================================================================

_PANEL_ES = {
    "xbar": "X-barra",
    "r": "R",
    "s": "S",
    "i": "de individuales",
    "mr": "de rangos móviles",
    "p": "p",
    "np": "np",
    "c": "c",
    "u": "u",
}
_DISPERSION_PANELS = {"r", "s", "mr"}
_CHART_TYPE_ES = {
    "xbar_r": "X-barra-R",
    "xbar_s": "X-barra-S",
    "i_mr": "I-MR",
    "p": "p",
    "np": "np",
    "c": "c",
    "u": "u",
}

# Qué suele significar cada patrón (Montgomery, cap. 5, sección de patrones
# en los gráficos de control, y Nelson, 1984).
_RULE_MEANING = {
    "WE1": "un punto fuera de los límites indica una causa asignable puntual (cambio de material, "
           "ajuste de máquina, error de medición o de registro)",
    "N1": "un punto fuera de los límites indica una causa asignable puntual (cambio de material, "
          "ajuste de máquina, error de medición o de registro)",
    "WE2": "dos de tres puntos más allá de 2 sigma sugieren un desplazamiento moderado del nivel",
    "N5": "dos de tres puntos en la zona A sugieren un desplazamiento moderado del nivel",
    "WE3": "cuatro de cinco puntos más allá de 1 sigma sugieren un desplazamiento pequeño pero "
           "sostenido del nivel",
    "N6": "cuatro de cinco puntos en la zona B o más allá sugieren un desplazamiento pequeño pero "
          "sostenido del nivel",
    "WE4": "una racha larga de un mismo lado indica que el nivel del proceso cambió y se mantuvo "
           "(nuevo lote de materia prima, otro operario, cambio de método)",
    "N2": "una racha larga de un mismo lado indica que el nivel del proceso cambió y se mantuvo "
          "(nuevo lote de materia prima, otro operario, cambio de método)",
    "N3": "una tendencia de puntos crecientes o decrecientes apunta a un deterioro gradual: "
          "desgaste de herramienta, temperatura, fatiga o agotamiento de un insumo",
    "N4": "la alternancia sistemática arriba y abajo sugiere dos fuentes que se turnan (máquinas, "
          "turnos, proveedores) o un sobreajuste del operador",
    "N7": "demasiados puntos cerca de la línea central indican estratificación: los subgrupos "
          "mezclan fuentes con medias distintas y los límites quedaron demasiado anchos",
    "N8": "puntos a ambos lados y lejos de la línea central sugieren una mezcla de dos poblaciones "
          "(por ejemplo, dos máquinas con medias distintas)",
}


def _panel_positions(panel: Any, max_len: int) -> dict[int, int]:
    """Mapa índice de subgrupo -> posición en `values` del panel."""
    indices = _get(panel, "indices")
    values = _get(panel, "values") or []
    if indices:
        return {int(i): k for k, i in enumerate(indices)}
    offset = max_len - len(values) if _get(panel, "name") == "mr" else 0
    return {k + offset: k for k in range(len(values))}


def _limits_text(panel: Any) -> str:
    c, u, l = (_get(panel, k) or [] for k in ("center", "ucl", "lcl"))
    if not c:
        return ""
    if max(u) - min(u) < 1e-12 and max(l) - min(l) < 1e-12:
        return f"LC = {fmt(c[0])}, LCS = {fmt(u[0])}, LCI = {fmt(l[0])}"
    return (
        f"LC = {fmt(c[0])}; límites por punto (tamaño de muestra variable), LCS entre "
        f"{fmt(min(u))} y {fmt(max(u))}, LCI entre {fmt(min(l))} y {fmt(max(l))}"
    )


def interpret_control_chart(
    charts: Sequence[Any],
    phase: str,
    chart_type: Optional[str] = None,
    limits: Any = None,
    in_control: Optional[bool] = None,
    out_of_control_points: Optional[Sequence[int]] = None,
    chart_warnings: Sequence[str] = (),
    rules: Optional[Sequence[str]] = None,
) -> Interpretation:
    """Interpreta un gráfico de control a partir de sus paneles y señales.

    - `charts`: paneles (`Panel` de `phases.py`, `ChartSeries` o dicts) con
      name, labels, values, center, ucl, lcl, violations y excluded.
    - `phase`: "I" o "II".
    - `limits`: parámetros congelados (para citar los excluidos y sus causas).
    - `chart_warnings`: advertencias ya generadas por el cálculo del gráfico.
    """
    charts = list(charts)
    findings: list[str] = []
    warnings: list[str] = list(chart_warnings)
    max_len = max((len(_get(p, "values") or []) for p in charts), default=0)
    type_name = _CHART_TYPE_ES.get(chart_type or "", chart_type or "de control")

    flagged = sorted(
        set(out_of_control_points)
        if out_of_control_points is not None
        else {int(_get(v, "index")) for p in charts for v in (_get(p, "violations") or [])}
    )
    if in_control is None:
        in_control = not flagged

    # Etiqueta por índice de subgrupo (del panel más largo)
    main = max(charts, key=lambda p: len(_get(p, "values") or [])) if charts else None
    main_labels = list(_get(main, "labels") or []) if main is not None else []

    def lab(i: int) -> str:
        return main_labels[i] if 0 <= i < len(main_labels) else str(i + 1)

    excluded_info = list(_get(limits, "excluded") or []) if limits is not None else []
    excluded_idx = sorted(
        {int(_get(e, "index")) for e in excluded_info}
        | {int(i) for p in charts for i in (_get(p, "excluded") or [])}
    )

    # Hallazgos por panel
    first_signal: Optional[tuple[int, str, str]] = None
    dispersion_signals = False
    for p in charts:
        name = _get(p, "name")
        pname = _PANEL_ES.get(name, name)
        values = list(_get(p, "values") or [])
        viols = list(_get(p, "violations") or [])
        pos = _panel_positions(p, max_len)
        findings.append(f"Gráfico {pname}: {_limits_text(p)}; {len(values)} puntos graficados.")
        if not viols:
            findings.append(f"Gráfico {pname}: ningún punto muestra señales con las reglas aplicadas.")
            continue
        if name in _DISPERSION_PANELS:
            dispersion_signals = True
        by_rule: dict[str, list[Any]] = {}
        for v in viols:
            by_rule.setdefault(_get(v, "rule"), []).append(v)
            idx = int(_get(v, "index"))
            if first_signal is None or idx < first_signal[0]:
                first_signal = (idx, _get(v, "rule"), pname)
        for rule, vs in by_rule.items():
            pts = []
            for v in vs[:8]:
                idx = int(_get(v, "index"))
                k = pos.get(idx)
                val = f" ({fmt(values[k])})" if k is not None and k < len(values) else ""
                pts.append(f"{lab(idx)}{val}")
            more = f" y {len(vs) - 8} más" if len(vs) > 8 else ""
            meaning = _RULE_MEANING.get(rule, "")
            findings.append(
                f"Gráfico {pname}, regla {rule}: señal en {'el subgrupo' if len(vs) == 1 else 'los subgrupos'} "
                f"{_join(pts)}{more}. {meaning[:1].upper() + meaning[1:]}." if meaning else
                f"Gráfico {pname}, regla {rule}: señal en {_join(pts)}{more}."
            )
        if name in _DISPERSION_PANELS:
            lows = []
            for v in viols:
                k = pos.get(int(_get(v, "index")))
                lcl = _get(p, "lcl") or []
                if k is not None and k < len(values) and k < len(lcl) and values[k] < lcl[k]:
                    lows.append(lab(int(_get(v, "index"))))
            findings.append(
                f"Las señales del gráfico {pname} indican que cambió la variabilidad "
                + (
                    f"(los subgrupos {_join(lows)} quedan por debajo del LCI: menos variación, que puede ser "
                    "una mejora o un problema del instrumento). "
                    if lows
                    else "dentro de los subgrupos. "
                )
                + "Los límites del gráfico de localización dependen de esa sigma: corrija primero la dispersión."
            )
        if name in ("p", "np", "c", "u"):
            lcl = _get(p, "lcl") or []
            lows = [
                lab(int(_get(v, "index")))
                for v in viols
                if pos.get(int(_get(v, "index"))) is not None
                and values[pos[int(_get(v, "index"))]] < lcl[pos[int(_get(v, "index"))]]
            ]
            if lows:
                findings.append(
                    f"Los puntos {_join(lows)} quedan por debajo del LCI: menos defectos de lo habitual. "
                    "Antes de celebrarlo, confirme que no cambió el criterio de inspección o el inspector."
                )

    for p in charts:
        skipped = _get(p, "rules_skipped") or {}
        for msg in skipped.values():
            text = f"Gráfico {_PANEL_ES.get(_get(p, 'name'), _get(p, 'name'))}: {msg}"
            if not any(msg in w for w in warnings):
                warnings.append(text)

    if excluded_info:
        causes = "; ".join(
            f"{_get(e, 'label') or lab(int(_get(e, 'index')))}: {_get(e, 'cause')}" for e in excluded_info
        )
        findings.append(
            f"Se excluyeron {len(excluded_info)} subgrupos del cálculo de límites por causa asignable "
            f"documentada ({causes}). Siguen graficados para que quede trazabilidad."
        )
    elif excluded_idx:
        findings.append(
            f"Se excluyeron del cálculo de límites los subgrupos {_join(lab(i) for i in excluded_idx)}."
        )

    rules_txt = f" con las reglas {_join(rules)}" if rules else ""
    n_points = max_len
    if phase == "I":
        used = _get(limits, "points_used") if limits is not None else None
        if in_control:
            summary = (
                f"Fase I del gráfico {type_name}: los {n_points} subgrupos están en control estadístico"
                f"{rules_txt}"
                + (f" tras excluir {len(excluded_idx)} con causa asignable" if excluded_idx else "")
                + ". Los límites pueden congelarse para monitorear la Fase II."
            )
        else:
            summary = (
                f"Fase I del gráfico {type_name}: {len(flagged)} de {n_points} subgrupos "
                f"{'muestra' if len(flagged) == 1 else 'muestran'} señales "
                f"({_join(lab(i) for i in flagged[:10])}{' y otros' if len(flagged) > 10 else ''}). "
                "Antes de congelar los límites hay que investigar cada señal, excluir solo las que "
                "tengan causa asignable documentada y recalcular."
            )
        if used is not None and int(used) < 20 and not any("20 a 25" in w for w in warnings):
            warnings.append(
                f"Los límites se estimaron con {used} subgrupos; Montgomery recomienda al menos 20 a 25 "
                "en Fase I para que los límites de prueba sean confiables."
            )
        if n_points and len(excluded_idx) > 0.2 * n_points:
            warnings.append(
                f"Se excluyó el {fmt_pct(len(excluded_idx) / n_points, 0)} de los subgrupos: con tantas "
                "causas asignables el proceso todavía no es estable y conviene corregirlo antes de "
                "fijar límites."
            )
        if not in_control:
            warnings.append(
                "Mientras haya señales sin explicar, la sigma estimada incluye causas especiales y "
                "los índices de capacidad no son válidos."
            )
    else:
        if in_control:
            summary = (
                f"Fase II del gráfico {type_name}: los {n_points} subgrupos nuevos se mantienen dentro de "
                f"los límites congelados{rules_txt}; el proceso sigue en control."
            )
        else:
            fs = first_signal
            summary = (
                f"Fase II del gráfico {type_name}: el proceso salió de control; hay señales en "
                f"{len(flagged)} de {n_points} subgrupos nuevos"
                + (
                    f" y la primera aparece en el subgrupo {lab(fs[0])} (gráfico {fs[2]}, regla {fs[1]})"
                    if fs
                    else ""
                )
                + ". Hay que buscar la causa asignable a partir de ese momento y actuar sobre el proceso."
            )
        warnings.append(
            "En Fase II los límites no se recalculan con los datos nuevos: si el proceso cambió de "
            "forma deliberada y permanente, debe repetirse la Fase I."
        )
    if dispersion_signals and charts and _get(charts[0], "name") not in _DISPERSION_PANELS:
        warnings.append(
            "Hay señales en el gráfico de dispersión: interprete el gráfico de localización con cautela, "
            "porque sus límites suponen una variabilidad estable."
        )
    return Interpretation(summary=summary, findings=findings, warnings=warnings)


def interpret_chart_result(result: Any, rules: Optional[Sequence[str]] = None) -> Interpretation:
    """Atajo para `ChartResult` de `phases.py` (o un `ChartResponse` sin interpretación)."""
    return interpret_control_chart(
        charts=_get(result, "charts") or [],
        phase=_get(result, "phase"),
        chart_type=_get(result, "chart_type"),
        limits=_get(result, "limits"),
        in_control=_get(result, "in_control"),
        out_of_control_points=_get(result, "out_of_control_points"),
        chart_warnings=_get(result, "warnings") or [],
        rules=rules,
    )
