"""Interpretación automática de resultados (conclusiones preliminares).

Cada función recibe un resultado ya calculado y devuelve un `Interpretation`
con tres partes, todas en español y con los números del caso:

- `summary`: una o dos frases con la conclusión principal.
- `findings`: qué pasó, dónde y qué implica para el proceso, uno por elemento.
- `warnings`: supuestos incumplidos y limitaciones del análisis.

Los números se escriben con coma decimal y espacio de miles (`fmt`); los
valores positivos muy pequeños, en notación científica.

Este módulo no importa los módulos de cálculo: lee los resultados por sus
atributos (o claves, si llegan como diccionarios), así que puede usarse con
las dataclasses de `spc` o con los modelos Pydantic del contrato.

Criterios de referencia (Montgomery, *Introduction to Statistical Quality
Control*):
- Capacidad: Cpk < 1 inadecuado; 1 a 1.33 marginal; 1.33 a 1.67 adecuado;
  >= 1.67 excelente. Esta escala es una convención de uso común (la del
  contrato), no una tabla del libro. Montgomery (cap. 8, tabla de valores
  mínimos recomendados del índice) pide 1.33 bilateral y 1.25 unilateral para
  procesos existentes, y 1.50 y 1.45 para procesos nuevos.
- Diseño de gráficos (cap. 6 y 7): ARL0 de 370.4 con límites de 3 sigma.
- Muestreo de aceptación (cap. 15): riesgo del productor α en AQL y del
  consumidor β en LTPD.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import NormalDist
from typing import Any, Iterable, Optional, Sequence


@dataclass
class Interpretation:
    summary: str
    findings: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# Formato de números
# --------------------------------------------------------------------------


_SUPERSCRIPT = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")


def _decimal_comma(s: str) -> str:
    """Punto decimal -> coma decimal (convención del español)."""
    return s.replace(".", ",")


def _scientific(x: float, digits: int) -> str:
    """Notación científica legible: 3,8·10⁻⁸."""
    mantissa, exponent = f"{x:.{max(digits - 1, 0)}e}".split("e")
    mantissa = mantissa.rstrip("0").rstrip(".") if "." in mantissa else mantissa
    return f"{_decimal_comma(mantissa)}·10{str(int(exponent)).translate(_SUPERSCRIPT)}"


def fmt(x: Optional[float], digits: int = 4) -> str:
    """Número con `digits` cifras significativas y coma decimal; 'no disponible'
    si es None o no finito.

    - Miles separados por espacio a partir de 10^digits ("123 457").
    - Valores con |x| < 0.0001 en notación científica ("3,8·10⁻⁸"), para que un
      número positivo pequeño nunca se imprima como "0" (hallazgo H13).
    """
    if x is None:
        return "no disponible"
    x = float(x)
    if not math.isfinite(x):
        return "no disponible"
    if x == 0:
        return "0"
    if abs(x) >= 10 ** digits:
        return f"{x:,.0f}".replace(",", " ")
    if abs(x) < 1e-4:
        return _scientific(x, digits)
    s = f"{x:.{digits}g}"
    if "e" in s:  # no debería ocurrir en este rango; por las dudas
        return _scientific(x, digits)
    return _decimal_comma(s)


def fmt_p(p: Optional[float]) -> str:
    """Valor p: cuatro decimales o '< 0,0001'."""
    if p is None:
        return "no disponible"
    if p < 0.0001:
        return "< 0,0001"
    return _decimal_comma(f"{p:.4f}")


def p_text(p: Optional[float]) -> str:
    """'p = 0,0245' o 'p < 0,0001' (sin el '= <')."""
    t = fmt_p(p)
    return f"p {t}" if t.startswith("<") else f"p = {t}"


def fmt_pct(x: Optional[float], digits: int = 2) -> str:
    """Porcentaje con coma decimal; un valor positivo que redondea a 0 se
    escribe como '< 0,01 %' en lugar de '0,00 %'."""
    if x is None:
        return "no disponible"
    v = 100 * float(x)
    if 0 < v < 0.5 * 10 ** (-digits):
        return f"< {_decimal_comma(f'{10 ** (-digits):.{digits}f}')} %"
    return f"{_decimal_comma(f'{v:.{digits}f}')} %"


def fmt_ppm(fraction: Optional[float]) -> str:
    if fraction is None:
        return "no disponible"
    ppm = fraction * 1e6
    if 0 < ppm < 0.001:
        return "< 0,001 PPM"
    if ppm >= 100:
        return f"{ppm:,.0f} PPM".replace(",", " ")
    return f"{_decimal_comma(f'{ppm:.3g}')} PPM"


def _plural(k: int, singular: str, plural: str) -> str:
    """'1 subgrupo', '2 subgrupos'."""
    return f"{k} {singular if k == 1 else plural}"


def _get(obj: Any, key: str, default: Any = None) -> Any:
    """Lee un atributo o una clave (dataclass, modelo Pydantic o dict)."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _join(items: Iterable[str], sep: str = ", ") -> str:
    """Une con comas y 'y'. Con números con coma decimal conviene sep='; '."""
    items = list(items)
    if len(items) <= 1:
        return "".join(items)
    return sep.join(items[:-1]) + " y " + items[-1]


# ==========================================================================
# Módulo 4. Supuestos
# ==========================================================================


def _expected_lags(x: float) -> str:
    """'se espera alrededor de 1 rezago' / 'se esperan unos 1,5 rezagos'."""
    t = fmt(x, 2)
    return f"se espera alrededor de {t} rezago" if t == "1" else f"se esperan unos {t} rezagos"


# Errores estándar de G1 y G2 bajo normalidad (Joanes y Gill, 1998, "Comparing
# measures of sample skewness and kurtosis", The Statistician 47, 183-189; son
# las fórmulas que usan SPSS y SAS):
#   EE(G1) = √(6n(n - 1) / ((n - 2)(n + 1)(n + 3)))
#   EE(G2) = √(4(n² - 1)·EE(G1)² / ((n - 3)(n + 5)))
# Un valor se describe como forma del proceso solo si |G| >= 1.96·EE.
_SHAPE_Z = 1.96


def _shape_standard_errors(n: int) -> tuple[Optional[float], Optional[float]]:
    se1 = math.sqrt(6 * n * (n - 1) / ((n - 2) * (n + 1) * (n + 3))) if n >= 3 else None
    se2 = math.sqrt(4 * (n * n - 1) * se1**2 / ((n - 3) * (n + 5))) if se1 is not None and n >= 4 else None
    return se1, se2


def _acf_chance(n: int, lags: Sequence[int], band: float) -> tuple[float, float]:
    """Número esperado de rezagos fuera de la banda ±`band` con datos i.i.d. y su
    desviación estándar si los rezagos fueran independientes.

    Usa la aproximación normal de r_k con E(r_k) ≈ -(n - k)/(n(n - 1)) y
    Var(r_k) ≈ (n - k)/(n(n + 2)), la varianza que pondera el estadístico de
    Ljung y Box (1978). No da la probabilidad de que salga al menos uno: los
    r_k no son independientes y esa probabilidad no se sigue de estos números
    (hallazgo H23; con n = 120 y m = 20 la simulación da 0.52, no 1 - 0.95^20 = 0.64).
    """
    if n < 3 or not lags:
        return 0.0, 0.0
    nd = NormalDist()
    probs = []
    for k in lags:
        if k >= n:
            continue
        mu = -(n - k) / (n * (n - 1))
        sd = math.sqrt((n - k) / (n * (n + 2)))
        probs.append(nd.cdf((-band - mu) / sd) + 1 - nd.cdf((band - mu) / sd))
    return float(sum(probs)), math.sqrt(sum(q * (1 - q) for q in probs))


def _verb(k: int, singular: str, plural: str) -> str:
    return singular if k == 1 else plural


def interpret_assumptions(result: Any, alpha: float = 0.05) -> Interpretation:
    """Interpreta normalidad e independencia (`AssumptionsResult`).

    Criterios de redacción (hallazgos H6 y S3 del validador):
    - No rechazar H0 no prueba el supuesto: se dice "no hay evidencia en contra
      con n = …", y con n pequeño se recuerda la poca potencia.
    - Un rechazo de Ljung-Box se describe por los rezagos que salen de banda y
      su signo. Solo se habla de autocorrelación positiva o negativa, y de un
      modelo AR(1), si el rezago 1 es significativo. Con muchos rezagos alguna
      salida de banda es esperable por azar.
    - Un rechazo de normalidad puede deberse a un proceso inestable.
    """
    d = _get(result, "descriptive")
    n = int(_get(d, "count"))
    normality = _get(result, "normality")
    independence = _get(result, "independence")
    is_normal = bool(_get(result, "is_normal"))
    is_independent = bool(_get(result, "is_independent"))
    ac = _get(result, "autocorrelation")
    a_txt = fmt(alpha, 3)
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
    se_g1, se_g2 = _shape_standard_errors(n)
    shape = []
    within = []
    if skew is not None and abs(skew) >= 0.5:
        side = "valores altos" if skew > 0 else "valores bajos"
        if se_g1 is not None and abs(skew) >= _SHAPE_Z * se_g1:
            shape.append(
                f"la asimetría es {fmt(skew, 3)} (error estándar {fmt(se_g1, 3)} con n = {n}), con "
                f"una cola más larga hacia {side}"
            )
        elif se_g1 is not None:
            within.append(f"asimetría {fmt(skew, 3)} (error estándar {fmt(se_g1, 3)})")
    if kurt is not None and abs(kurt) >= 1:
        if se_g2 is not None and abs(kurt) >= _SHAPE_Z * se_g2:
            se_txt = f" (error estándar {fmt(se_g2, 3)} con n = {n})"
            if kurt > 0:
                shape.append(
                    f"el exceso de curtosis es {fmt(kurt, 3)}{se_txt}: colas más pesadas que la "
                    "normal, con más valores extremos de los esperados"
                )
            else:
                shape.append(
                    f"el exceso de curtosis es {fmt(kurt, 3)}{se_txt}: colas más livianas que la "
                    "normal, lo que puede indicar mezcla de dos fuentes o datos truncados (por "
                    "ejemplo, piezas seleccionadas antes de medir)"
                )
        elif se_g2 is not None:
            within.append(f"exceso de curtosis {fmt(kurt, 3)} (error estándar {fmt(se_g2, 3)})")
    if shape:
        one = len(shape) == 1
        findings.append(
            "Forma de la distribución: " + "; ".join(shape) + ". "
            + ("El valor supera" if one else "Cada valor supera")
            + f" {fmt(_SHAPE_Z, 3)} veces su error estándar, así que es poco probable que "
            + ("sea" if one else "sean") + " solo ruido de muestreo."
        )
    if within:
        one = len(within) == 1
        findings.append(
            f"La muestra tiene {_join(within)}, pero con n = {n} "
            + ("ese valor está" if one else "esos valores están")
            + f" a menos de {fmt(_SHAPE_Z, 3)} errores estándar de 0, lo esperable en datos normales: "
            + ("describe esta muestra y no indica por sí solo" if one
               else "describen esta muestra y no indican por sí solos")
            + " colas ni asimetría en el proceso."
        )

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

    # ---------------------------------------------------------- independencia
    lags = list(_get(ac, "lags") or [])
    vals = list(_get(ac, "values") or [])
    band = float(_get(ac, "band"))
    sig = list(_get(ac, "significant_lags") or [])
    m = len(lags)
    r1 = vals[0] if vals else None
    r1_sig = 1 in sig
    n_acf = int(_get(ac, "n") or n)
    expected_out, sd_out = _acf_chance(n_acf, lags, band)
    chance_txt = (
        f"{_expected_lags(expected_out)} fuera de banda solo por azar (aproximación con la "
        "varianza (n - k)/(n(n + 2)) de cada autocorrelación)"
    )

    def lag_txt(k: int) -> str:
        return f"r{k} = {fmt(vals[lags.index(k)], 3)}"

    if sig:
        detail = _join((lag_txt(k) for k in sig[:6]), sep="; ")
        extra = f" (y {len(sig) - 6} más)" if len(sig) > 6 else ""
        pos = sum(1 for k in sig if vals[lags.index(k)] > 0)
        neg = len(sig) - pos
        if len(sig) == 1:
            signs = "positiva" if pos else "negativa"
        else:
            signs = (
                "todas positivas" if neg == 0 else "todas negativas" if pos == 0
                else f"{pos} positivas y {neg} negativas"
            )
        findings.append(
            f"La autocorrelación supera la banda ±{fmt(band, 3)} en {len(sig)} de {m} rezagos "
            f"({signs}): {detail}{extra}. Con {m} rezagos, n = {n_acf} y α = {a_txt} {chance_txt}."
        )
        if r1_sig and r1 > 0:
            findings.append(
                f"La autocorrelación de rezago 1 es positiva y significativa ({fmt(r1, 3)}): cada "
                "observación se parece a la anterior. Es típico de procesos continuos o de un "
                "muestreo más frecuente que la dinámica del proceso."
            )
        elif r1_sig and r1 < 0:
            findings.append(
                f"La autocorrelación de rezago 1 es negativa y significativa ({fmt(r1, 3)}): a un "
                "valor alto le sigue uno bajo, patrón típico de ajustes del operador después de "
                "cada medición."
            )
        else:
            findings.append(
                f"El rezago 1 no sale de la banda (r1 = {fmt(r1, 3)}): no hay evidencia de que cada "
                "observación dependa de la inmediatamente anterior. Un rezago k aislado fuera de "
                "banda puede reflejar un patrón que se repite cada k observaciones (posición "
                "dentro del subgrupo, cavidad, turno) o ser casual."
            )
    else:
        findings.append(
            f"Ningún rezago entre 1 y {m} supera la banda ±{fmt(band, 3)} de la función de "
            "autocorrelación."
        )
    for t in independence:
        findings.append(f"{_get(t, 'name')}: {_get(t, 'conclusion')}")

    by_name = {_get(t, "name"): t for t in independence}
    lb = by_name.get("Ljung-Box")
    runs = by_name.get("Rachas")
    rejected_ind = [t for t in independence if _get(t, "reject")]
    many_lags = len(sig) > expected_out + 2 * sd_out
    strong_dependence = (not is_independent) and (
        r1_sig or len(rejected_ind) == len(independence) or many_lags
    )

    def test_p(t: Any) -> str:
        name = "rachas" if _get(t, "name") == "Rachas" else _get(t, "name")
        return f"{name}, {p_text(_get(t, 'p_value'))}"

    # ------------------------------------------------------------ advertencias
    rejected_norm = [_get(t, "name") for t in normality if _get(t, "reject")]
    if not is_normal:
        warnings.append(
            f"Se rechaza la normalidad ({_join(rejected_norm)}). Los índices de capacidad y la "
            "fracción no conforme esperada suponen normalidad y no serán confiables. Antes de "
            "transformar los datos, confirme con un gráfico de control que el proceso está en "
            "control: un proceso con desplazamientos de la media mezcla varias normales y también "
            "hace rechazar estas pruebas, aunque cada tramo sea normal. Si el proceso es estable, "
            "conviene transformar los datos (por ejemplo, Box-Cox), ajustar otra distribución o "
            "apoyarse en la fracción no conforme observada. El gráfico de individuales es el más "
            "sensible a este problema; el de X-barra con n >= 4 lo es menos por el teorema central "
            "del límite."
        )
        if len(rejected_norm) < len(normality):
            warnings.append(
                "Las pruebas de normalidad no coinciden: Anderson-Darling da más peso a las colas "
                "y Shapiro-Wilk a la forma general. Revise el histograma y el gráfico Q-Q antes de decidir."
            )
    if not is_independent:
        if r1_sig and r1 > 0:
            warnings.append(
                f"Hay autocorrelación positiva de rezago 1 (r1 = {fmt(r1, 3)}). Con ella, la sigma "
                "estimada con rangos móviles o dentro de subgrupos subestima la variabilidad y los "
                "límites de Shewhart producen falsas alarmas frecuentes. Montgomery (cap. 10) "
                "recomienda modelar la serie (por ejemplo, un AR(1)) y graficar los residuos, o "
                "espaciar más las muestras."
            )
        elif r1_sig and r1 < 0:
            warnings.append(
                f"Hay autocorrelación negativa de rezago 1 (r1 = {fmt(r1, 3)}). Con ella, el rango "
                "móvil sobrestima la sigma y los límites de individuales quedan demasiado anchos: "
                "el gráfico pierde sensibilidad. Suele deberse a ajustes del operador tras cada "
                "medición; Montgomery (cap. 10) recomienda modelar la serie y graficar los residuos."
            )
        else:
            outside = (
                f"; salen de banda {_join((lag_txt(k) for k in sig[:6]), sep='; ')}" if sig
                else "; ningún rezago sale de la banda"
            )
            warnings.append(
                f"La evidencia contra la independencia no viene del rezago 1 (r1 = {fmt(r1, 3)}, "
                f"dentro de la banda ±{fmt(band, 3)}){outside}. Con {m} rezagos y α = {a_txt} "
                f"{chance_txt}, así que un rezago aislado fuera de banda no es raro, y con muchos "
                "rezagos el tamaño real de Ljung-Box es algo mayor que α. No alcanza para elegir un "
                "modelo de la serie: "
                "confirme con más datos o revisando el orden de muestreo."
            )
        if len(rejected_ind) < len(independence):
            warnings.append(
                "La conclusión de independencia combina dos pruebas: aunque cada una tiene nivel "
                f"α = {a_txt}, la probabilidad de que alguna rechace por azar con datos "
                "independientes es mayor (del orden del 7 % al 13 % con α = 0,05)."
            )
    elif sig:
        warnings.append(
            f"Algunos rezagos salen de la banda pero las pruebas globales no rechazan la "
            f"independencia. Con {m} rezagos y α = {a_txt} {chance_txt}."
        )
    if not is_independent or sig:
        warnings.append(
            "Ljung-Box, la autocorrelación y las rachas suponen observaciones igualmente "
            "espaciadas en el tiempo. Si la serie concatena subgrupos (varias piezas seguidas y "
            "luego una pausa) o tiene huecos porque se excluyeron subgrupos, el rezago k no "
            "corresponde siempre al mismo intervalo y estas pruebas son aproximadas."
        )
    if n < 20:
        warnings.append(
            f"Con solo {n} observaciones las pruebas tienen poca potencia: solo detectan desvíos "
            "grandes, y no rechazar H0 no demuestra que el supuesto se cumpla."
        )
    if n > 5000:
        warnings.append(
            "Con más de 5000 observaciones las pruebas rechazan ante desvíos mínimos sin "
            "importancia práctica; juzgue la normalidad también por el gráfico Q-Q."
        )

    # ----------------------------------------------------------------- resumen
    low_power = (
        f" Con solo {n} datos las pruebas tienen poca potencia y solo detectarían desvíos grandes."
        if n < 20 else ""
    )
    if is_normal and is_independent:
        summary = (
            f"Las {n} observaciones son compatibles con la normalidad y con la independencia: "
            f"ninguna prueba rechaza al nivel α = {a_txt}. Eso significa que no hay evidencia en "
            "contra de los supuestos de los gráficos de Shewhart y de los índices de capacidad "
            f"con n = {n}, no que esté demostrado que se cumplan." + low_power
        )
        return Interpretation(summary=summary, findings=findings, warnings=warnings)

    if is_normal:
        norm_txt = "no hay evidencia contra la normalidad"
    else:
        norm_txt = (
            f"hay evidencia contra la normalidad ({_join(rejected_norm)} "
            f"{_verb(len(rejected_norm), 'rechaza', 'rechazan')})"
        )
    if is_independent:
        ind_txt = "no hay evidencia contra la independencia"
    else:
        tests = _join((test_p(t) for t in rejected_ind), sep="; ")
        if sig:
            lag_part = (
                f"{_plural(len(sig), 'rezago', 'rezagos')} de {m} fuera de la banda: "
                f"{_join((lag_txt(k) for k in sig[:4]), sep='; ')}"
            )
        else:
            lag_part = "ningún rezago fuera de la banda"
        if strong_dependence:
            ind_txt = f"hay evidencia de autocorrelación ({tests}; {lag_part})"
        else:
            others = [t for t in independence if not _get(t, "reject")]
            other_txt = (
                "; " + _join((f"{test_p(t)}, no rechaza" for t in others), sep="; ") if others else ""
            )
            ind_txt = (
                f"la evidencia contra la independencia es débil ({tests}{other_txt}; {lag_part}, "
                f"cuando con {m} rezagos y datos independientes {_expected_lags(expected_out)} "
                "fuera de banda por azar, de modo que uno aislado no es raro)"
            )
    summary = f"Con {n} observaciones, {norm_txt} y {ind_txt}."
    if not is_normal:
        summary += (
            " Los índices de capacidad y las PPM esperadas basados en la normal no son confiables "
            "con datos no normales; antes de transformarlos, confirme que el proceso está en "
            "control, porque un proceso inestable también produce este rechazo."
        )
    if not is_independent and strong_dependence:
        summary += (
            " Con autocorrelación, los límites de Shewhart calculados con la sigma de corto plazo "
            "no tienen la tasa de falsas alarmas nominal: conviene entender y modelar la "
            "dependencia antes de controlar el proceso."
        )
    elif not is_independent:
        summary += (
            " No alcanza para afirmar que las observaciones estén autocorrelacionadas; conviene "
            "confirmarlo con más datos o revisando cómo se ordenaron las mediciones."
        )
    if not is_normal and is_independent:
        summary += " Los gráficos de control pueden usarse con cautela."
    summary += low_power
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


def _lot_defectives(p: float, lot_size: int) -> int:
    """D = floor(p·N + 0.5), la misma regla que `sampling.defectives_in_lot`."""
    return int(math.floor(round(p * lot_size, 9) + 0.5))


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
            verdict = (
                f" No cumple los riesgos pactados; el plan n = {n}, c = {c} sí. Si el plan de "
                "referencia se leyó en un nomograma o se obtuvo con una aproximación, la diferencia "
                "se explica porque esa lectura es aproximada y no garantiza los riesgos; aquí cada "
                f"plan se verificó con la distribución {_DIST_NAMES.get(dist, dist).split(' (')[0]} exacta."
            )
        findings.append(
            f"Plan de referencia n = {rn}, c = {rc}: {_join(parts, sep='; ') if parts else 'sin AQL ni LTPD para comparar'}.{verdict}"
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
        used = [
            f"{label} = {fmt_pct(p)} da D = {_lot_defectives(p, lot_size)}"
            for label, p in (("AQL", aql), ("LTPD", ltpd)) if p is not None
        ]
        warnings.append(
            f"Con la hipergeométrica la fracción defectuosa se traduce en D = redondeo(p·{lot_size}) "
            "unidades defectuosas del lote (redondeo hacia arriba en ,5), así que α y β corresponden "
            "a ese número entero" + (f": {_join(used, sep='; ')}." if used else ".")
        )
        if aql is not None and _lot_defectives(aql, lot_size) == 0:
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


# Reglas que pueden señalar un nivel más bajo sin que un punto cruce el LCI:
# rachas de un lado, tendencias y zonas (si el gráfico las aplica).
_DOWNWARD_RULES = {"WE2", "WE3", "WE4", "N2", "N3", "N5", "N6", "N8"}


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
                f"El ARL0 real es {fmt(arl0, 4)}, no el nominal {fmt(NOMINAL_ARL0_3SIGMA)} de los límites "
                "de 3 sigma con la normal. El conteo es discreto y asimétrico: la probabilidad de "
                f"falsa alarma queda en {fmt(alpha, 4)} en lugar de 0,0027"
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
            applied = list((simulation or {}).get("applied") or []) if method == "simulation" else []
            beyond = [r for r in applied if r in _DOWNWARD_RULES]
            lower_rows = [r for r in rows if float(_get(r, "shift")) < center]
            if not beyond:
                which = (
                    "con la regla de un punto fuera de límites" if not applied or set(applied) <= _POINT_RULES
                    else f"con las reglas aplicadas ({_join(applied)}), ninguna de las cuales busca "
                    "rachas o zonas por debajo de la línea central,"
                )
                findings.append(
                    f"El límite inferior es 0, así que {which} el gráfico no puede señalar mejoras "
                    "(disminuciones de la fracción o de la media de defectos)"
                    + (
                        "; las filas con valores menores al de control muestran ARL1 muy grandes por "
                        "esa razón." if lower_rows else "."
                    )
                )
            else:
                example = ""
                if lower_rows:
                    r0 = lower_rows[0]
                    example = (
                        f": ante {_shift_label(chart, float(_get(r0, 'shift')), center)} el ARL1 es "
                        f"{fmt(_get(r0, 'arl1'), 4)} muestras"
                    )
                one = len(beyond) == 1
                findings.append(
                    "El límite inferior es 0, así que un punto fuera de límites solo puede señalar "
                    f"aumentos. {'La regla' if one else 'Las reglas'} {_join(beyond)} "
                    f"{'mira' if one else 'miran'} también los puntos por debajo de la línea central, "
                    f"de modo que el gráfico sí puede señalar mejoras{example}."
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
            f", ATS1 = {_hours(float(_get(r, 'ats1')))} y unidades inspeccionadas hasta la señal: "
            f"{fmt(float(_get(r, 'units_to_detect')), 4)}"
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
        f"Carga muestral: {_count(load, 'unidad inspeccionada', 'unidades inspeccionadas')} por hora. "
        "Es el costo que se compara "
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
            se0 = float(simulation.get("arl0_std_error") or 0.0)
            no_change = abs(sh0 - arl0) <= 2 * se0
            if no_change:
                text = (
                    f"Solo con la regla de un punto fuera de límites el ARL0 sería {fmt(sh0, 4)}: la "
                    f"diferencia con el ARL0 simulado ({fmt(arl0, 4)} ± {fmt(se0, 3)}) está dentro del "
                    "error de simulación, así que las reglas suplementarias no aumentan las falsas "
                    "alarmas de forma apreciable"
                )
            else:
                text = (
                    f"Solo con la regla de un punto fuera de límites el ARL0 sería {fmt(sh0, 4)}: las "
                    f"reglas suplementarias multiplican las falsas alarmas por {fmt(ratio, 3)}"
                )
            sh1 = simulation.get("shewhart_arl1") or []
            if focus is not None and sh1:
                idx = rows.index(focus)
                if idx < len(sh1) and sh1[idx] is not None:
                    shift_txt = _shift_label(chart, float(_get(focus, 'shift')), center)
                    text += (
                        f"; ante {shift_txt} el ARL1 es {fmt(_get(focus, 'arl1'), 4)} muestras, frente a "
                        f"{fmt(sh1[idx], 4)} solo con esa regla" if no_change else
                        f", a cambio de detectar {shift_txt} "
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
            "No se enviaron estados fuera de control; se evaluaron 1,5; 2; 2,5 y 3 veces el valor en control."
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

# Escala de cuatro categorías del contrato: convención de uso común, no una
# tabla de Montgomery (hallazgo S1).
VERDICT_ES = {
    "inadequate": "inadecuado (Cpk < 1)",
    "marginal": "marginal (1 <= Cpk < 1,33)",
    "adequate": "adecuado (1,33 <= Cpk < 1,67)",
    "excellent": "excelente (Cpk >= 1,67)",
}

# Montgomery, cap. 8, tabla de valores mínimos recomendados del índice de
# capacidad para procesos existentes: 1.33 con especificación bilateral y 1.25
# con especificación unilateral (1.50 y 1.45 para procesos nuevos).
_MIN_EXISTING = {True: 1.33, False: 1.25}

_SIGMA_METHOD_ES = {
    "rbar_d2": "R̄/d2",
    "sbar_c4": "S̄/c4",
    "mrbar_d2": "MR̄/d2",
    "frozen_limits": "los parámetros congelados de Fase I",
}


def _iv(index: Any) -> tuple[Optional[float], Optional[float], Optional[float]]:
    return _get(index, "value"), _get(index, "lower"), _get(index, "upper")


def _poisson_sf(k: int, lam: float) -> float:
    """P(X >= k) con X ~ Poisson(lam), sumando términos (k moderado)."""
    if k <= 0:
        return 1.0
    term = math.exp(-lam)
    cdf = term
    for i in range(1, k):
        term *= lam / i
        cdf += term
    return max(0.0, 1.0 - cdf)


def interpret_capability(
    result: Any,
    lsl: Optional[float] = None,
    usl: Optional[float] = None,
    target: Optional[float] = None,
    confidence: float = 0.95,
    is_stable: Optional[bool] = None,
    is_normal: Optional[bool] = None,
    subgroup_count: Optional[int] = None,
    sigma_dof: Optional[float] = None,
    limits: Any = None,
) -> Interpretation:
    """Interpreta un análisis de capacidad (`CapabilityResult`).

    `sigma_dof` es ν, los grados de libertad efectivos de la sigma de corto
    plazo (`capability.sigma_dof`); `limits`, los límites congelados si se
    usaron. Criterios (hallazgos H1, H7, H9, H14, S1, S4 y S5 del validador):
    - Sin estabilidad confirmada el resumen no declara capaz al proceso: la
      reserva va primero y el veredicto se presenta como condicional.
    - Las afirmaciones "con 95 % de confianza Cpk supera…" usan la cota
      unilateral Ĉ - z_{1-α}·EE, no el extremo del intervalo bilateral.
    - La razón σ_largo/σ_corto se compara con lo esperable por azar:
      Var(ln σ̂_o - ln σ̂_w) ≈ 1/(2ν) - 1/(2(N - 1)), porque la desviación
      muestral es el estimador eficiente bajo normalidad e independencia y la
      covarianza con un estimador menos eficiente es igual a su varianza (con
      sigma congelada son independientes y las varianzas se suman).
    """
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
    two_sided = lsl is not None and usl is not None
    req = _MIN_EXISTING[two_sided]
    side_word = "bilateral" if two_sided else "unilateral"
    frozen = method == "frozen_limits"
    nu = float(sigma_dof) if sigma_dof is not None else None
    findings: list[str] = []
    warnings: list[str] = []

    if two_sided:
        specs = f"especificaciones [{fmt(lsl)}; {fmt(usl)}]"
    elif lsl is not None:
        specs = f"límite inferior de especificación {fmt(lsl)}"
    else:
        specs = f"límite superior de especificación {fmt(usl)}"

    # ------------------------------------------------------------- resumen
    cpk_txt = f"Cpk = {fmt(cpk, 3)}" + (
        f" (IC {conf}: {fmt(cpk_lo, 3)} a {fmt(cpk_hi, 3)})" if cpk_lo is not None else ""
    )
    verdict_txt = VERDICT_ES.get(verdict, verdict)
    ppm_txt = fmt_ppm(_get(ew, "total"))
    req_core = (
        f"mínimo de {fmt(req, 3)} que Montgomery (cap. 8) recomienda para procesos "
        f"existentes con especificación {side_word}"
    )
    req_txt = "el " + req_core
    lb1 = None
    if cpk_lo is not None and cpk is not None and cpk_hi is not None:
        nd = NormalDist()
        se_cpk = (cpk - cpk_lo) / nd.inv_cdf(1 - (1 - confidence) / 2)
        lb1 = cpk - nd.inv_cdf(confidence) * se_cpk
    if is_stable is False:
        reasons = ["el proceso no está en control estadístico"]
        if is_normal is False:
            reasons.append("los datos no son normales")
        summary = (
            "El proceso no está en control estadístico, así que no se puede declarar su capacidad: "
            f"con {specs}, {cpk_txt} no describe lo que el proceso producirá (solo en un proceso "
            f"estable correspondería al veredicto de capacidad {verdict_txt}). Estos índices no son confiables "
            f"porque {_join(reasons)}; primero hay que eliminar las causas asignables y repetir el "
            "estudio."
        )
    elif is_stable is None:
        summary = (
            "No se confirmó que el proceso esté en control estadístico, así que el veredicto es "
            f"condicional: con {specs}, {cpk_txt}, que correspondería al veredicto de capacidad {verdict_txt} "
            "solo si el proceso es estable; en ese caso se esperarían "
            f"{ppm_txt} fuera de especificación con la variación de corto plazo."
        )
        if is_normal is False:
            summary += " Además, estos índices no son confiables porque los datos no son normales."
    elif is_normal is False:
        summary = (
            "Estos índices no son confiables porque los datos no son normales: con "
            f"{specs}, {cpk_txt} correspondería al veredicto de capacidad {verdict_txt} y a {ppm_txt} fuera "
            "de especificación solo si la distribución fuera normal. La fracción observada fuera "
            f"de especificación es {fmt_pct(_get(ob, 'total'))}."
        )
    elif lb1 is not None and cpk >= req > lb1:
        # S7: la estimación puntual cumple el mínimo pero la cota unilateral no.
        summary = (
            f"Con {specs}, {cpk_txt}: según la estimación puntual, veredicto de capacidad "
            f"{verdict_txt}, pero no es concluyente: la cota inferior de confianza unilateral del "
            f"{conf} es {fmt(lb1, 3)}, por debajo del {req_core}, así que con estos datos no se puede "
            f"afirmar con {conf} de confianza que el proceso lo cumpla. Con la variación de corto "
            f"plazo se espera {ppm_txt} fuera de especificación."
        )
    else:
        summary = (
            f"Con {specs}, {cpk_txt}: veredicto de capacidad {verdict_txt}. Con la variación de "
            f"corto plazo se espera {ppm_txt} fuera de especificación."
        )

    # ------------------------------------------------------------ hallazgos
    nu_txt = f", ν ≈ {fmt(nu, 3)} grados de libertad efectivos" if nu is not None else ""
    findings.append(
        f"Se usaron {n} observaciones"
        + (f" en {subgroup_count} subgrupos" if subgroup_count and subgroup_count != n else "")
        + f": media {fmt(mean)}, sigma de corto plazo {fmt(sw)} (estimada con "
        f"{_SIGMA_METHOD_ES.get(method, method)}{nu_txt}) y sigma de largo plazo {fmt(so)} "
        f"(desviación muestral de todos los datos, {n - 1} grados de libertad)."
    )

    if cp is not None:
        used = 100 / cp if cp > 0 else None
        ci = f" (IC {conf}: {fmt(cp_lo, 3)} a {fmt(cp_hi, 3)})" if cp_lo is not None else ""
        findings.append(
            f"Cp = {fmt(cp, 3)}{ci}: la tolerancia {fmt(usl - lsl)} equivale a {fmt(cp, 3)} veces la "
            f"dispersión natural 6σ = {fmt(6 * sw)}; el proceso ocupa el {fmt(used, 3)} % del "
            "intervalo de especificación."
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
            f"{fmt(cpk, 3)}, la distancia de la media al límite en unidades de 3σ. Para una "
            f"especificación unilateral Montgomery (cap. 8) recomienda un mínimo de 1,25 en procesos "
            "existentes; la escala del veredicto (1, 1,33 y 1,67) es una convención de uso común."
        )

    if cpk is not None and cpk < 0:
        warnings.append(
            f"Cpk es negativo ({fmt(cpk, 3)}): la media del proceso está fuera de la especificación. "
            "Más de la mitad de la producción queda fuera; la acción urgente es reubicar la media."
        )

    if lb1 is not None:
        firm = is_stable is True and is_normal is not False
        if lb1 >= req and firm:
            findings.append(
                f"La cota inferior de confianza unilateral del {conf} para Cpk es {fmt(lb1, 3)}: con "
                f"{conf} de confianza Cpk supera {req_txt}. (El intervalo bilateral, {fmt(cpk_lo, 3)} "
                f"a {fmt(cpk_hi, 3)}, es el rango de valores de Cpk compatibles con los datos.)"
            )
        elif lb1 >= req:
            # H20: sin estabilidad confirmada (o con datos no normales) Cpk no es un
            # parámetro del proceso futuro y la cota no se puede afirmar.
            if is_stable is False:
                why = "el proceso no está en control estadístico, así que Cpk no describe un proceso predecible"
            elif is_stable is None:
                why = "no se confirmó que el proceso esté en control estadístico"
            else:
                why = "los datos no son normales y el intervalo supone normalidad"
            findings.append(
                f"La cota inferior de confianza unilateral del {conf} para Cpk sería {fmt(lb1, 3)}, por "
                f"encima del {req_core}, si el proceso fuera estable y normal. Como {why}, esa cota no "
                "permite afirmar que el proceso cumpla el mínimo: es solo lo que valdría la "
                "conclusión una vez confirmados esos supuestos."
            )
        elif cpk >= req:
            findings.append(
                f"Aunque la estimación puntual de Cpk ({fmt(cpk, 3)}) supera {fmt(req, 3)}, la cota "
                f"inferior de confianza unilateral del {conf} es {fmt(lb1, 3)}: con estos datos{nu_txt} "
                f"para sigma, no se puede afirmar con {conf} de confianza que el proceso cumpla "
                f"{req_txt}."
            )
        elif cpk_hi < 1:
            findings.append(
                f"Incluso el límite superior del intervalo de Cpk ({fmt(cpk_hi, 3)}) es menor que 1: "
                "la falta de capacidad no se explica por el error de muestreo."
            )
        else:
            findings.append(
                f"El intervalo de Cpk va de {fmt(cpk_lo, 3)} a {fmt(cpk_hi, 3)}: la estimación puntual "
                f"está por debajo del {req_core}, pero con estos datos no se puede descartar un Cpk "
                "real algo mayor o menor; la conclusión firme es que el proceso no "
                "demuestra la capacidad requerida."
            )

    if pp is not None or ppk is not None:
        ratio = so / sw
        between = (
            "variación de largo plazo que el rango móvil no capta (desplazamientos o derivas lentas "
            "de la media)" if method == "mrbar_d2"
            else "una variabilidad actual mayor que la de la Fase I o variación entre subgrupos"
            if frozen
            else "variación entre subgrupos (desplazamientos o derivas de la media en el tiempo)"
        )
        if nu is not None and n > 1:
            var = 1 / (2 * nu) + (1 if frozen else -1) / (2 * (n - 1))
            var = max(var, 1 / (2 * nu) * 0.05)
            z95 = NormalDist().inv_cdf(0.95)
            upper = math.exp(z95 * math.sqrt(var))
            lower = math.exp(-z95 * math.sqrt(var))
            chance = (
                f"con N = {n} y ν ≈ {fmt(nu, 3)}, en un proceso estable la razón superaría "
                f"{fmt(upper, 3)} solo alrededor del 5 % de las veces"
            )
        else:
            upper, lower, chance = None, None, None
        if ratio > max(1.10, upper or 1.10):
            findings.append(
                f"La sigma de largo plazo es {fmt(ratio, 3)} veces la de corto plazo, así que Ppk = "
                f"{fmt(ppk, 3)} queda por debajo de Cpk = {fmt(cpk, 3)}"
                + (f"; la diferencia es mayor que la esperable por azar ({chance})" if chance else "")
                + f". Es un indicio de {between}: confírmelo en el gráfico de control; eliminar "
                "esas causas acercaría el desempeño real a la capacidad potencial."
                + ("" if chance else " Sin los grados de libertad de la sigma de corto plazo no se "
                   "puede juzgar si la diferencia excede el azar.")
            )
        elif ratio > 1.10:
            findings.append(
                f"La sigma de largo plazo es {fmt(ratio, 3)} veces la de corto plazo (Ppk = "
                f"{fmt(ppk, 3)}, Cpk = {fmt(cpk, 3)}), pero {chance}: esta diferencia es compatible "
                f"con el azar y no es evidencia de {between}."
            )
        elif ratio < min(0.90, lower or 0.90):
            cause = (
                "autocorrelación negativa (valores que oscilan de uno a otro) que infla el rango móvil"
                if method == "mrbar_d2"
                else "subgrupos mal formados (mezcla de fuentes dentro del subgrupo) o un estimador "
                "de corto plazo inflado"
            )
            findings.append(
                f"La sigma de largo plazo es menor que la de corto plazo (razón {fmt(ratio, 3)}), algo "
                "poco habitual"
                + (" y más de lo esperable por azar" if chance else "")
                + f": puede indicar {cause}."
            )
        else:
            findings.append(
                f"Las sigmas de corto ({fmt(sw)}) y largo plazo ({fmt(so)}) son similares (razón "
                f"{fmt(ratio, 3)}): Ppk = {fmt(ppk, 3)} y Cpk = {fmt(cpk, 3)} cuentan la misma "
                "historia; no hay indicios de grandes desplazamientos entre subgrupos."
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
    elif target is not None:
        warnings.append(
            f"El objetivo T = {fmt(target)} está fuera de las especificaciones ({specs}): Cpm no se "
            "calculó porque un objetivo que no cumple la especificación no tiene sentido como valor "
            "nominal. Revise si el objetivo o los límites se cargaron bien."
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
    exp_count = float(_get(eo, "total")) * n
    if n_out == 0 and exp_count < 1:
        findings.append(
            f"No se observó ninguna unidad fuera de especificación, coherente con lo esperado: con "
            f"{n} datos solo cabría esperar ver alguna si la fracción no conforme fuera del orden de "
            f"1/{n} ({fmt_pct(1 / n)}) o mayor, así que la fracción observada no sirve para "
            "confirmar niveles de PPM bajos."
        )
    elif n_out > 0 and _poisson_sf(n_out, exp_count) < 0.01:
        warnings.append(
            f"Se observaron {n_out} datos fuera de especificación frente a {fmt(exp_count, 3)} "
            "esperados con la normal y la sigma de largo plazo (una diferencia así ocurre por azar "
            "menos del 1 % de las veces). Puede deberse a colas más pesadas que las del modelo o a "
            "inestabilidad del proceso (desplazamientos que sacan tramos de datos de "
            "especificación); en ambos casos las PPM esperadas subestiman el problema."
        )

    # ---------------------------------------------------------- advertencias
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
    if n < 50 or (nu is not None and nu < 50):
        warnings.append(
            f"Con {n} observaciones"
            + (f" y ν ≈ {fmt(nu, 3)} grados de libertad para la sigma de corto plazo" if nu is not None else "")
            + " los intervalos de confianza son anchos; para conclusiones firmes se recomiendan "
            "estudios de capacidad con 100 datos o más."
        )
    method_es = _SIGMA_METHOD_ES.get(method, method)
    if frozen and nu is None:
        warnings.append(
            "Los límites congelados no informan con cuántos subgrupos, de qué tamaño o con qué "
            "método se estimó sigma en la Fase I (points_used, subgroup_size, sigma_method), así que "
            "no se conocen sus grados de libertad y los intervalos de Cp y Cpk no se calcularon. "
            f"Usar los N - 1 = {n - 1} grados de libertad de los datos nuevos daría intervalos "
            "aproximados pero demasiado estrechos, porque sigma no se volvió a estimar con ellos."
        )
    elif frozen:
        m1 = _get(limits, "points_used") if limits is not None else None
        k1 = _get(limits, "subgroup_size") if limits is not None else None
        origin = (
            f" ({m1} subgrupos" + (f" de n = {k1}" if k1 and int(k1) > 1 else "") + ")"
            if m1 is not None else ""
        )
        warnings.append(
            f"La sigma de corto plazo es la congelada de la Fase I{origin}: sus grados de libertad "
            f"efectivos son ν ≈ {fmt(nu, 3)}, no los N - 1 = {n - 1} de los datos nuevos, porque "
            "sigma no se volvió a estimar. Los intervalos de Cp y Cpk usan ese ν, son aproximados y "
            "suponen que la variabilidad no cambió desde la Fase I."
        )
    elif nu is not None:
        warnings.append(
            f"Los intervalos de Cp y Cpk usan ν ≈ {fmt(nu, 3)} grados de libertad efectivos de la "
            f"sigma estimada con {method_es}, no N - 1 = {n - 1}: la fórmula del libro supone la "
            "desviación muestral, y con este estimador los intervalos son aproximados "
            "(aproximación chi-cuadrado con la misma variabilidad relativa del estimador)."
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
    "N8": "ocho puntos seguidos lejos de la línea central, ninguno dentro de 1 sigma: si quedan a "
          "ambos lados sugieren una mezcla de dos poblaciones (por ejemplo, dos máquinas con medias "
          "distintas); si quedan todos del mismo lado indican un desplazamiento del nivel",
}

_N8_MIXTURE = ("ocho puntos seguidos lejos de la línea central y a ambos lados, ninguno dentro de 1 "
               "sigma, sugieren una mezcla de dos poblaciones (por ejemplo, dos máquinas con medias "
               "distintas)")
_N8_SHIFT = ("ocho puntos seguidos lejos de la línea central y todos del mismo lado indican un "
             "desplazamiento del nivel del proceso, no una mezcla")

# Reglas de racha o de patrón sin zonas. Solo WE4 y N2 (rachas de un lado)
# dependen de P(punto sobre la LC), que en paneles asimétricos (R, S, MR y
# atributos) no es 0.5; N3 y N4 dependen solo del orden y su ARL0 (421.6 y
# 601.0) no cambia con la asimetría en un estadístico continuo i.i.d.
# (hallazgos H5 y H18).
_RUN_RULES = {"WE4", "N2", "N3", "N4"}
_SIDE_RUN_RULES = {"WE4", "N2"}
_POINT_RULES = {"WE1", "N1"}
_ATTRIBUTE_PANELS = {"p", "np", "c", "u"}
_ASYMMETRIC_PANELS = _DISPERSION_PANELS | _ATTRIBUTE_PANELS


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
    u_const = max(u) - min(u) < 1e-12
    l_const = max(l) - min(l) < 1e-12
    if u_const and l_const:
        return f"LC = {fmt(c[0])}, LCS = {fmt(u[0])}, LCI = {fmt(l[0])}"
    u_txt = f"LCS = {fmt(u[0])}" if u_const else f"LCS entre {fmt(min(u))} y {fmt(max(u))}"
    if l_const:
        l_txt = f"LCI = {fmt(l[0])} en todos los puntos" + (" (truncado en 0)" if abs(l[0]) < 1e-12 else "")
    else:
        l_txt = f"LCI entre {fmt(min(l))} y {fmt(max(l))}"
    return f"LC = {fmt(c[0])}; límites por punto (tamaño de muestra variable), {u_txt}, {l_txt}"


def _side_run_caution(pname: str, name: str, rules: Sequence[str], values: Sequence[float],
                      center: Sequence[float]) -> str:
    """Cautela para WE4 y N2 en un panel asimétrico (hallazgos H18 y H19).

    Solo las rachas de un lado dependen de P(punto sobre la LC). N3 y N4
    dependen solo del orden y no se nombran aquí. En R y S (continuos) la
    probabilidad no es 1/2 y el ARL0 baja (más falsas alarmas). En conteos,
    si la LC coincide con un valor posible, los puntos iguales a la LC cortan
    la racha y el ARL0 sube mucho (WE4 con c̄ = 2: 1 924 frente a 255).
    """
    one = len(rules) == 1
    ids = _join(rules)
    head = f"En el gráfico {pname} la distribución del estadístico es asimétrica"
    caveat = (
        f" Tome {'esa señal' if one else 'esas señales'} como un indicio que hay que confirmar con "
        "más datos o con puntos fuera de límites, no como prueba de un cambio."
    )
    rule_txt = f"{'la regla' if one else 'las reglas'} de racha de un lado ({ids})"
    verb_more = "da" if one else "dan"
    if name in _DISPERSION_PANELS:
        return (
            f"{head} (gráfico de dispersión): la probabilidad de quedar sobre la línea central no es "
            f"0,5, así que {rule_txt} {verb_more} falsas alarmas más a menudo que en un gráfico "
            "simétrico." + caveat
        )
    ties = [k for k in range(min(len(values), len(center)))
            if abs(values[k] - center[k]) <= 1e-9 * max(1.0, abs(center[k]))]
    integer_cl = name in ("c", "np") and bool(center) and all(
        abs(cv - round(cv)) <= 1e-9 * max(1.0, abs(cv)) for cv in center)
    if ties or integer_cl:
        tie_txt = (
            f"; {_plural(len(ties), 'punto cae', 'puntos caen')} exactamente sobre ella" if ties else ""
        )
        return (
            f"{head} (gráfico de atributos) y la línea central ({fmt(center[0])}) coincide con un "
            f"valor posible del conteo{tie_txt}. Los puntos iguales a la línea central cortan la "
            f"racha, así que {rule_txt} {verb_more} menos falsas alarmas que la nominal (su ARL0 "
            "queda por encima del de un gráfico simétrico) y también pierde sensibilidad: una señal "
            f"{'suya' if one else 'de ellas'} es más difícil de obtener por azar, pero que no aparezca "
            "dice poco sobre si el nivel cambió. Aun así, confirme la causa antes de actuar."
        )
    if name in ("c", "np"):
        return (
            f"{head} (gráfico de atributos): la línea central ({fmt(center[0])}) no es un valor "
            "posible del conteo y la probabilidad de quedar sobre ella no es 0,5, así que "
            f"{rule_txt} {verb_more} falsas alarmas más a menudo que en un gráfico simétrico." + caveat
        )
    return (
        f"{head} (gráfico de atributos): la probabilidad de quedar sobre la línea central no es "
        f"0,5 y algunos conteos pueden caer exactamente sobre ella y cortar la racha, así que la "
        f"tasa de falsas alarmas de {rule_txt} es distinta de la nominal: mayor si la línea central "
        "no es un valor posible del conteo y posiblemente mucho menor si lo es." + caveat
    )


def _skipped_messages(panel: Any) -> list[str]:
    skipped = _get(panel, "rules_skipped") or {}
    if isinstance(skipped, dict):
        return [str(v) for v in skipped.values()]
    return [str(_get(item, "reason")) for item in skipped]


def _many_rules_warning(rules: Optional[Sequence[str]], charts: Sequence[Any]) -> Optional[str]:
    """S6: con varias reglas a la vez la tasa de falsas alarmas conjunta sube.

    Referencias para un estadístico normal i.i.d. con L = 3: WE1 sola, ARL0 =
    370,4; WE1 a WE4, 91,75 (Champ y Woodall, 1987, cadena de Markov; el módulo
    de diseño da 91,5 ± 1,3 por simulación); las 12 reglas, 65,5 ± 0,9 por
    simulación con el módulo de diseño (5000 corridas, semilla 12345).
    """
    if rules:
        used = list(dict.fromkeys(str(r) for r in rules))
    else:
        used = list(dict.fromkeys(str(r) for p in charts for r in (_get(p, "rules_applied") or [])))
    extra = [r for r in used if r not in _POINT_RULES]
    if not extra:
        return None
    k = len(used)
    return (
        f"Se aplicaron {k} reglas a la vez ({_join(used)}). Cada regla agrega su propia "
        "probabilidad de falsa alarma, así que la tasa conjunta es mayor que la de cualquiera por "
        "separado: con un estadístico normal y el proceso en control, WE1 sola da una falsa alarma "
        "cada 370 puntos en promedio, las cuatro reglas de Western Electric juntas cada 92 (Champ "
        "y Woodall, 1987) y las 12 reglas juntas cada 66 aproximadamente. Una señal aislada de una "
        "regla suplementaria puede ser una falsa alarma; el ARL0 de esta combinación se puede "
        "calcular en el módulo de diseño."
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
      En Fase II sus exclusiones son de la Fase I: se citan como origen de los
      límites, no como puntos graficados (hallazgo H4).
    - `chart_warnings`: advertencias ya generadas por el cálculo del gráfico.
    """
    charts = list(charts)
    findings: list[str] = []
    warnings: list[str] = list(chart_warnings)
    max_len = max((len(_get(p, "values") or []) for p in charts), default=0)
    type_name = _CHART_TYPE_ES.get(chart_type or "", chart_type or "de control")
    # En I-MR no hay subgrupos: cada punto es una observación (hallazgo H24).
    individual = chart_type == "i_mr" or any(_get(p, "name") == "mr" for p in charts)
    sg, sgs = ("punto", "puntos") if individual else ("subgrupo", "subgrupos")

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
    if phase == "I":
        excluded_idx = sorted(
            {int(_get(e, "index")) for e in excluded_info}
            | {int(i) for p in charts for i in (_get(p, "excluded") or [])}
        )
    else:
        excluded_idx = sorted({int(i) for p in charts for i in (_get(p, "excluded") or [])})

    # Hallazgos por panel
    first_signal: Optional[tuple[int, str, str]] = None
    dispersion_signals = False
    low_side: dict[int, bool] = {}  # índice -> todas sus señales son "por debajo del LCI"
    for p in charts:
        name = _get(p, "name")
        pname = _PANEL_ES.get(name, name)
        values = list(_get(p, "values") or [])
        center = list(_get(p, "center") or [])
        lcl = list(_get(p, "lcl") or [])
        viols = list(_get(p, "violations") or [])
        pos = _panel_positions(p, max_len)
        findings.append(f"Gráfico {pname}: {_limits_text(p)}; {len(values)} puntos graficados.")
        if not viols:
            findings.append(f"Gráfico {pname}: ningún punto muestra señales con las reglas aplicadas.")
            continue

        def below_lcl(v: Any) -> bool:
            k = pos.get(int(_get(v, "index")))
            return (
                _get(v, "rule") in _POINT_RULES and k is not None and k < len(values)
                and k < len(lcl) and values[k] < lcl[k]
            )

        for v in viols:
            idx = int(_get(v, "index"))
            low_side[idx] = low_side.get(idx, True) and below_lcl(v) and name in _ASYMMETRIC_PANELS
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
            if rule == "N8":
                sides = set()
                for v in vs:
                    k = pos.get(int(_get(v, "index")))
                    if k is None:
                        continue
                    for j in range(max(0, k - 7), k + 1):
                        if j < len(values) and j < len(center):
                            sides.add(values[j] > center[j])
                if sides == {True} or sides == {False}:
                    meaning = _N8_SHIFT
                elif len(sides) == 2:
                    meaning = _N8_MIXTURE
            where = f"el {sg}" if len(vs) == 1 else f"los {sgs}"
            findings.append(
                f"Gráfico {pname}, regla {rule}: señal en {where} {_join(pts, sep='; ')}{more}. "
                f"{meaning[:1].upper() + meaning[1:]}." if meaning else
                f"Gráfico {pname}, regla {rule}: señal en {where} {_join(pts, sep='; ')}{more}."
            )
        rules_here = set(by_rule)
        run_only = rules_here <= _RUN_RULES
        side_here = sorted(rules_here & _SIDE_RUN_RULES)
        if name in _ASYMMETRIC_PANELS and side_here:
            findings.append(_side_run_caution(pname, name, side_here, values, center))
        if name == "mr":
            if not run_only:
                dispersion_signals = True
            highs = [int(_get(v, "index")) for v in viols if _get(v, "rule") in _POINT_RULES]
            if highs:
                pairs = [f"{lab(i - 1)} y {lab(i)}" for i in highs[:6]]
                more_mr = f" y {len(highs) - 6} más" if len(highs) > 6 else ""
                findings.append(
                    f"Los rangos móviles fuera de límites ({'entre las observaciones' if len(highs) == 1 else 'entre los pares de observaciones'} "
                    f"{_join(pairs, sep='; ')}{more_mr}) indican un salto grande entre dos "
                    "observaciones consecutivas: un dato atípico, un error de registro o un cambio de "
                    "nivel; revise esas observaciones en el gráfico de individuales para distinguirlos. "
                    "Un rango móvil grande aislado no demuestra que haya cambiado la variabilidad del proceso. "
                    "Como MR̄ fija los límites del gráfico de individuales, revise ese dato antes de "
                    "interpretar el resto."
                )
        elif name in _DISPERSION_PANELS:
            if not run_only:
                dispersion_signals = True
            lows = [lab(int(_get(v, "index"))) for v in viols if below_lcl(v)]
            if run_only:
                findings.append(
                    f"Las señales del gráfico {pname} son solo de racha o tendencia: podrían reflejar un "
                    "cambio de la variabilidad dentro de los subgrupos, pero sin puntos fuera de "
                    "límites no bastan para afirmarlo."
                )
            else:
                if lows:
                    low_txt = (
                        f"(el subgrupo {lows[0]} queda por debajo del LCI" if len(lows) == 1
                        else f"(los subgrupos {_join(lows)} quedan por debajo del LCI"
                    ) + ": menos variación, que puede ser una mejora o un problema del instrumento). "
                else:
                    low_txt = "dentro de los subgrupos. "
                findings.append(
                    f"Los puntos fuera de límites del gráfico {pname} indican que cambió la "
                    f"variabilidad {low_txt}Los límites del gráfico de localización dependen de esa "
                    "sigma: corrija primero la dispersión."
                )
        if name in _ATTRIBUTE_PANELS:
            lows = [lab(int(_get(v, "index"))) for v in viols if below_lcl(v)]
            if lows:
                head = (
                    f"El punto {lows[0]} queda por debajo del LCI" if len(lows) == 1
                    else f"Los puntos {_join(lows)} quedan por debajo del LCI"
                )
                findings.append(
                    f"{head}: menos defectos de lo habitual, una posible mejora. Antes de celebrarlo, "
                    "confirme que no cambió el criterio de inspección o el inspector; si la mejora es "
                    "real, identifique su causa para mantenerla."
                )

    for p in charts:
        for msg in _skipped_messages(p):
            text = f"Gráfico {_PANEL_ES.get(_get(p, 'name'), _get(p, 'name'))}: {msg}"
            if not any(msg in w for w in warnings):
                warnings.append(text)

    def causes_text() -> str:
        return "; ".join(
            f"{_get(e, 'label') or lab(int(_get(e, 'index')))}: {_get(e, 'cause')}" for e in excluded_info
        )

    used = _get(limits, "points_used") if limits is not None else None
    if phase == "I":
        if excluded_info:
            k = len(excluded_info)
            findings.append(
                f"{'Se excluyó' if k == 1 else 'Se excluyeron'} {_plural(k, sg, sgs)} "
                f"del cálculo de límites por causa asignable documentada ({causes_text()}). "
                f"{'Sigue graficado' if k == 1 else 'Siguen graficados'} para que quede trazabilidad."
            )
        elif excluded_idx:
            k = len(excluded_idx)
            findings.append(
                f"{'Se excluyó' if k == 1 else 'Se excluyeron'} del cálculo de límites "
                f"{'el ' + sg if k == 1 else 'los ' + sgs} {_join(lab(i) for i in excluded_idx)}."
            )
    elif excluded_info or used:
        k = len(excluded_info)
        origin = f"Los límites congelados se estimaron en la Fase I"
        if used:
            origin += f" con {_plural(int(used), sg + ' retenido', sgs + ' retenidos')}"
        if excluded_info:
            causes = "; ".join(
                f"{_get(e, 'label') or f'{sg} {int(_get(e, 'index')) + 1} de la Fase I'}: {_get(e, 'cause')}"
                for e in excluded_info
            )
            origin += (
                f", después de excluir {_plural(k, sg, sgs)} por causa asignable "
                f"({causes})"
            )
        findings.append(origin + ". Esas exclusiones son de la Fase I y no forman parte de este gráfico.")

    rules_txt = f" con las reglas {_join(rules)}" if rules else ""
    if phase == "I":
        n_retained = max_len - len([i for i in excluded_idx if 0 <= i < max_len])
        if in_control:
            if excluded_idx:
                k = len(excluded_idx)
                summary = (
                    f"Fase I del gráfico {type_name}: los {n_retained} {sgs} retenidos están en "
                    f"control estadístico{rules_txt} ({'se excluyó' if k == 1 else 'se excluyeron'} "
                    f"{_plural(k, sg, sgs)} con causa asignable de los {max_len} "
                    "graficados). Los límites pueden congelarse para monitorear la Fase II."
                )
            else:
                summary = (
                    f"Fase I del gráfico {type_name}: los {max_len} {sgs} están en control "
                    f"estadístico{rules_txt}. Los límites pueden congelarse para monitorear la Fase II."
                )
        else:
            summary = (
                f"Fase I del gráfico {type_name}: {len(flagged)} de los {max_len} {sgs} graficados "
                f"{'muestra' if len(flagged) == 1 else 'muestran'} señales "
                f"({_join(lab(i) for i in flagged[:10])}{' y otros' if len(flagged) > 10 else ''}). "
                "Antes de congelar los límites hay que investigar cada señal, excluir solo las que "
                "tengan causa asignable documentada y recalcular."
            )
        if used is not None and int(used) < 20 and not any("20 a 25" in w for w in warnings):
            warnings.append(
                f"Los límites se estimaron con {used} {sgs}; Montgomery recomienda al menos 20 a 25 "
                "en Fase I para que los límites de prueba sean confiables."
            )
        if max_len and len(excluded_idx) > 0.2 * max_len:
            warnings.append(
                f"Se excluyó el {fmt_pct(len(excluded_idx) / max_len, 0)} de los {sgs}: con tantas "
                "causas asignables el proceso todavía no es estable y conviene corregirlo antes de "
                "fijar límites."
            )
        if not in_control:
            warnings.append(
                "Mientras haya señales sin explicar, la sigma estimada incluye causas especiales y "
                "los índices de capacidad no son válidos."
            )
    else:
        improvement_only = bool(flagged) and all(low_side.get(i, False) for i in flagged)
        if in_control:
            summary = (
                f"Fase II del gráfico {type_name}: los {max_len} {sgs} nuevos se mantienen dentro de "
                f"los límites congelados{rules_txt}; el proceso sigue en control."
            )
        elif improvement_only:
            k = len(flagged)
            pts = _join(lab(i) for i in flagged[:10])
            summary = (
                f"Fase II del gráfico {type_name}: "
                + (f"el {sg} {pts} queda" if k == 1 else f"{k} de {max_len} {sgs} nuevos ({pts}) quedan")
                + " por debajo del límite inferior, la única señal"
                + (" del gráfico" if k == 1 else "s del gráfico")
                + ". Es una posible mejora, no un motivo para corregir el proceso: confirme que no "
                "cambió la inspección o el instrumento y, si la mejora es real, identifique su causa "
                "para mantenerla"
                + (" (un solo punto puede ser también una falsa alarma)." if k == 1 else ".")
            )
        else:
            fs = first_signal
            summary = (
                f"Fase II del gráfico {type_name}: el proceso salió de control; hay señales en "
                f"{len(flagged)} de {max_len} {sgs} nuevos"
                + (
                    f" y la primera aparece en el {sg} {lab(fs[0])} (gráfico {fs[2]}, regla {fs[1]})"
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
        if any(_get(p, "name") == "mr" for p in charts):
            warnings.append(
                "Hay rangos móviles fuera de límites: MR̄ incluye ese salto y ensancha los límites del "
                "gráfico de individuales; interprételo con cautela hasta revisar el dato."
            )
        else:
            warnings.append(
                "Hay señales en el gráfico de dispersión: interprete el gráfico de localización con "
                "cautela, porque sus límites suponen una variabilidad estable."
            )
    many = _many_rules_warning(rules, charts)
    if many:
        warnings.append(many)
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
