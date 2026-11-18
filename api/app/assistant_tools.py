"""Herramientas que el asistente puede invocar. Envuelven funciones de `app/spc/`.

Reglas:
- Las entradas vienen del modelo: se validan y se acotan aquí antes de llamar a `spc/`.
- Solo método exacto (sin simulación), para acotar el tiempo de la función.
- Las salidas son compactas (sin curvas) y sin NaN ni infinito.
- Un error de validación devuelve `ToolError` con un mensaje en español; el bucle del
  asistente lo entrega al modelo como `tool_result` con `is_error`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable

from app.spc import design as spc_design
from app.spc import sampling as spc_sampling

# --- Límites (cada herramienta corre en la función serverless) -------------------
MAX_N = 200  # tamaño de subgrupo
MAX_LIST = 8  # elementos de cualquier lista de entrada
MAX_COMBINATIONS = 32  # filas de la comparación de diseños
MAX_PLAN_N = 100_000  # tamaño de muestra de un plan de aceptación
MAX_LOT = 10_000_000
MIN_PROPORTION = 1e-5  # AQL, LTPD y p0 mínimos


class ToolError(ValueError):
    """Entrada inválida: el mensaje (en español) se muestra al modelo."""


@dataclass(frozen=True)
class Tool:
    name: str
    label: str
    description: str
    schema: dict[str, Any]
    run: Callable[[dict[str, Any]], dict[str, Any]]

    def definition(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.schema,
            "eager_input_streaming": True,
        }


# --- Validación ---------------------------------------------------------------
def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _number(args: dict, key: str, lo: float, hi: float, default: float | None = None) -> float:
    value = args.get(key, default)
    if value is None:
        raise ToolError(f"Falta el parámetro «{key}».")
    if not _is_number(value) or not lo <= value <= hi:
        raise ToolError(f"«{key}» debe ser un número entre {lo:g} y {hi:g}.")
    return float(value)


def _integer(args: dict, key: str, lo: int, hi: int, default: int | None = None) -> int:
    value = args.get(key, default)
    if value is None:
        raise ToolError(f"Falta el parámetro «{key}».")
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if not isinstance(value, int) or isinstance(value, bool) or not lo <= value <= hi:
        raise ToolError(f"«{key}» debe ser un entero entre {lo} y {hi}.")
    return value


def _optional_integer(args: dict, key: str, lo: int, hi: int) -> int | None:
    return None if args.get(key) is None else _integer(args, key, lo, hi)


def _optional_number(args: dict, key: str, lo: float, hi: float) -> float | None:
    return None if args.get(key) is None else _number(args, key, lo, hi)


def _number_list(args: dict, key: str, lo: float, hi: float, default: list | None = None, integers: bool = False) -> list:
    values = args.get(key, default)
    if values is None:
        raise ToolError(f"Falta el parámetro «{key}».")
    if not isinstance(values, list) or not 1 <= len(values) <= MAX_LIST:
        raise ToolError(f"«{key}» debe ser una lista de 1 a {MAX_LIST} números.")
    out = []
    for item in values:
        out.append(_integer({key: item}, key, int(lo), int(hi)) if integers else _number({key: item}, key, lo, hi))
    return out


def _choice(args: dict, key: str, options: tuple[str, ...], default: str | None = None) -> str:
    value = args.get(key, default)
    if value not in options:
        raise ToolError(f"«{key}» debe ser una de estas opciones: {', '.join(options)}.")
    return value


def _clean(value: Any, digits: int = 4) -> Any:
    """Redondea y sustituye NaN e infinito por None."""
    if isinstance(value, float):
        return round(value, digits) if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: _clean(v, digits) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v, digits) for v in value]
    return value


# --- 1. ARL / ATS de un diseño --------------------------------------------------
def run_arl(args: dict[str, Any]) -> dict[str, Any]:
    chart = _choice(args, "chart", ("xbar", "individuals", "p", "c"))
    n = _integer(args, "n", 1, MAX_N, default=1)
    width = _number(args, "limit_width", 1.0, 6.0, default=3.0)
    h = _number(args, "sampling_interval", 0.01, 720.0, default=1.0)
    kwargs: dict[str, Any] = {}
    if chart in ("xbar", "individuals"):
        kwargs["shifts"] = _number_list(args, "shifts", 0.1, 6.0, default=[0.5, 1.0, 1.5, 2.0, 3.0])
    elif chart == "p":
        kwargs["p0"] = _number(args, "p0", MIN_PROPORTION, 0.5)
        kwargs["p1"] = (
            _number_list(args, "p1", MIN_PROPORTION, 0.99) if args.get("p1") is not None else None
        )
    else:
        kwargs["c0"] = _number(args, "c0", 0.01, 1000.0)
        kwargs["c1"] = _number_list(args, "c1", 0.01, 5000.0) if args.get("c1") is not None else None
    result = spc_design.compute_arl(
        chart, n=n, limit_width=width, sampling_interval=h, rules=["WE1"], **kwargs
    )
    return _clean(
        {
            "metodo": result.method,
            "alfa_por_muestra": result.alpha,
            "arl0": result.arl0,
            "ats0_horas": result.ats0,
            "carga_muestral_unidades_por_hora": result.sampling_load,
            "desplazamientos": [
                {
                    "desplazamiento": r.shift,
                    "beta": r.beta,
                    "arl1": r.arl1,
                    "ats1_horas": r.ats1,
                    "unidades_hasta_detectar": r.units_to_detect,
                }
                for r in result.rows
            ],
            "advertencias": result.interpretation.warnings[:3],
        }
    )


# --- 2. Comparación de diseños X-barra ----------------------------------------
def run_compare(args: dict[str, Any]) -> dict[str, Any]:
    n_values = _number_list(args, "n_values", 1, MAX_N, integers=True)
    widths = _number_list(args, "limit_widths", 1.0, 6.0, default=[3.0])
    intervals = _number_list(args, "sampling_intervals", 0.01, 720.0, default=[1.0])
    shift = _number(args, "shift", 0.1, 6.0, default=1.0)
    if len(n_values) * len(widths) * len(intervals) > MAX_COMBINATIONS:
        raise ToolError(f"Demasiadas combinaciones: el máximo es {MAX_COMBINATIONS} diseños por consulta.")
    result = spc_design.compare_designs(n_values, limit_widths=widths, sampling_intervals=intervals, shift=shift)
    return _clean(
        {
            "desplazamiento_sigmas": result.shift,
            "disenos": [
                {
                    "n": r.n,
                    "L": r.limit_width,
                    "h_horas": r.sampling_interval,
                    "arl0": r.arl0,
                    "ats0_horas": r.ats0,
                    "arl1": r.arl1,
                    "ats1_horas": r.ats1,
                    "carga_muestral_unidades_por_hora": r.sampling_load,
                }
                for r in result.rows
            ],
        }
    )


# --- 3 y 4. Planes de muestreo de aceptación ----------------------------------
_DISTRIBUTIONS = ("binomial", "poisson", "hypergeometric")


def _plan_summary(plan: Any) -> dict[str, Any]:
    return _clean(
        {
            "n": plan.n,
            "c": plan.c,
            "distribucion": plan.distribution,
            "alfa_real": plan.alpha_actual,
            "beta_real": plan.beta_actual,
            "aoql": plan.aoql,
            "aoql_en_fraccion_defectuosa": plan.aoql_at,
            "advertencias": plan.interpretation.warnings[:3],
        },
        digits=5,
    )


def run_design_plan(args: dict[str, Any]) -> dict[str, Any]:
    aql = _number(args, "aql", MIN_PROPORTION, 0.5)
    ltpd = _number(args, "ltpd", MIN_PROPORTION * 2, 0.9)
    if not aql < ltpd:
        raise ToolError("El AQL debe ser menor que el LTPD.")
    if ltpd / aql < 1.5:
        raise ToolError("El LTPD debe ser al menos 1,5 veces el AQL; si no, el plan resultante sería enorme.")
    alpha = _number(args, "alpha", 0.001, 0.5, default=0.05)
    beta = _number(args, "beta", 0.001, 0.5, default=0.10)
    lot = _optional_integer(args, "lot_size", 2, MAX_LOT)
    distribution = _choice(args, "distribution", _DISTRIBUTIONS, default="binomial")
    plan = spc_sampling.design_single_plan(
        aql, ltpd, alpha=alpha, beta=beta, lot_size=lot, distribution=distribution
    )
    return _plan_summary(plan)


def run_evaluate_plan(args: dict[str, Any]) -> dict[str, Any]:
    n = _integer(args, "n", 1, MAX_PLAN_N)
    c = _integer(args, "c", 0, MAX_PLAN_N)
    aql = _optional_number(args, "aql", MIN_PROPORTION, 0.5)
    ltpd = _optional_number(args, "ltpd", MIN_PROPORTION, 0.99)
    lot = _optional_integer(args, "lot_size", 2, MAX_LOT)
    distribution = _choice(args, "distribution", _DISTRIBUTIONS, default="binomial")
    plan = spc_sampling.evaluate_single_plan(
        n, c, lot_size=lot, distribution=distribution, aql=aql, ltpd=ltpd
    )
    return _plan_summary(plan)


# --- Catálogo -------------------------------------------------------------------
TOOLS: dict[str, Tool] = {
    t.name: t
    for t in (
        Tool(
            name="calcular_arl_ats",
            label="Calculando ARL y ATS del diseño",
            description=(
                "Calcula con fórmulas exactas el ARL0 (muestras hasta una falsa alarma), el ARL1, el ATS "
                "(horas hasta señalar) y la carga muestral de un gráfico de control Shewhart con la regla de "
                "un punto fuera de límites. Úsala para evaluar un tamaño de subgrupo n, un ancho de límites L "
                "y un intervalo h concretos. No simula y no incluye reglas de corrida suplementarias."
            ),
            schema={
                "type": "object",
                "properties": {
                    "chart": {"type": "string", "enum": ["xbar", "individuals", "p", "c"],
                              "description": "Tipo de gráfico: X-barra, individuales, p o c"},
                    "n": {"type": "integer", "minimum": 1, "maximum": MAX_N,
                          "description": "Tamaño de subgrupo (xbar y p); se ignora en individuals y c"},
                    "limit_width": {"type": "number", "description": "Ancho de límites L en sigmas (por defecto 3)"},
                    "sampling_interval": {"type": "number", "description": "Intervalo entre muestras h, en horas (por defecto 1)"},
                    "shifts": {"type": "array", "items": {"type": "number"}, "maxItems": MAX_LIST,
                               "description": "xbar e individuals: desplazamientos de la media en sigmas, p. ej. [0.5, 1, 2]"},
                    "p0": {"type": "number", "description": "Gráfico p: fracción defectuosa en control"},
                    "p1": {"type": "array", "items": {"type": "number"}, "maxItems": MAX_LIST,
                           "description": "Gráfico p: fracciones desplazadas; si se omite, 1,5 a 3 veces p0"},
                    "c0": {"type": "number", "description": "Gráfico c: media de defectos en control"},
                    "c1": {"type": "array", "items": {"type": "number"}, "maxItems": MAX_LIST,
                           "description": "Gráfico c: medias desplazadas; si se omite, 1,5 a 3 veces c0"},
                },
                "required": ["chart"],
            },
            run=run_arl,
        ),
        Tool(
            name="comparar_disenos_xbar",
            label="Comparando diseños de gráfico X-barra",
            description=(
                "Compara alternativas de diseño de un gráfico X-barra (varios n, L y h) para un desplazamiento "
                "de la media que se quiere detectar: devuelve ARL0, ATS0, ARL1, ATS1 y carga muestral n/h de "
                "cada combinación. Úsala para explicar el compromiso entre detección y carga de inspección."
            ),
            schema={
                "type": "object",
                "properties": {
                    "n_values": {"type": "array", "items": {"type": "integer"}, "minItems": 1, "maxItems": MAX_LIST,
                                 "description": "Tamaños de subgrupo a comparar"},
                    "limit_widths": {"type": "array", "items": {"type": "number"}, "maxItems": 4,
                                     "description": "Anchos L (por defecto [3])"},
                    "sampling_intervals": {"type": "array", "items": {"type": "number"}, "maxItems": 4,
                                           "description": "Intervalos h en horas (por defecto [1])"},
                    "shift": {"type": "number", "description": "Desplazamiento a detectar en sigmas (por defecto 1)"},
                },
                "required": ["n_values"],
            },
            run=run_compare,
        ),
        Tool(
            name="disenar_plan_muestreo",
            label="Diseñando el plan de muestreo de aceptación",
            description=(
                "Diseña el plan simple de muestreo de aceptación (n, c) de menor tamaño que cumple el riesgo del "
                "productor alfa en el AQL y el riesgo del consumidor beta en el LTPD, y devuelve los riesgos "
                "reales y el AOQL. AQL y LTPD son fracciones (1 % = 0,01)."
            ),
            schema={
                "type": "object",
                "properties": {
                    "aql": {"type": "number", "description": "Nivel de calidad aceptable, fracción defectuosa"},
                    "ltpd": {"type": "number", "description": "Calidad límite, fracción defectuosa (mayor que el AQL)"},
                    "alpha": {"type": "number", "description": "Riesgo del productor (por defecto 0,05)"},
                    "beta": {"type": "number", "description": "Riesgo del consumidor (por defecto 0,10)"},
                    "lot_size": {"type": "integer", "description": "Tamaño de lote N; obligatorio con hipergeométrica"},
                    "distribution": {"type": "string", "enum": list(_DISTRIBUTIONS),
                                     "description": "Por defecto binomial"},
                },
                "required": ["aql", "ltpd"],
            },
            run=run_design_plan,
        ),
        Tool(
            name="evaluar_plan_muestreo",
            label="Evaluando el plan de muestreo",
            description=(
                "Evalúa un plan simple (n, c) que ya se tiene: devuelve su alfa real en el AQL y su beta real "
                "en el LTPD (si se dan) y su AOQL."
            ),
            schema={
                "type": "object",
                "properties": {
                    "n": {"type": "integer", "description": "Tamaño de muestra"},
                    "c": {"type": "integer", "description": "Número de aceptación"},
                    "aql": {"type": "number", "description": "Fracción defectuosa AQL (opcional)"},
                    "ltpd": {"type": "number", "description": "Fracción defectuosa LTPD (opcional)"},
                    "lot_size": {"type": "integer", "description": "Tamaño de lote N (opcional)"},
                    "distribution": {"type": "string", "enum": list(_DISTRIBUTIONS)},
                },
                "required": ["n", "c"],
            },
            run=run_evaluate_plan,
        ),
    )
}


def tool_definitions() -> list[dict[str, Any]]:
    """Lista estable y en orden fijo (parte del prefijo cacheable)."""
    return [t.definition() for t in TOOLS.values()]
