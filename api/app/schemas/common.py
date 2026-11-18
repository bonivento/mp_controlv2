"""Tipos compartidos por todos los módulos del contrato.

Este paquete (`app.schemas`) es el CONTRATO entre el frontend y el backend.
De aquí se genera el OpenAPI y los tipos TypeScript de `web/lib/api-types.ts`.
Solo la sesión principal lo modifica; los agentes proponen cambios, no los aplican.

Convenciones:
- Los índices de puntos son base 0 y se refieren a la posición del subgrupo
  en el orden en que llegó en la petición.
- Las probabilidades y fracciones van en escala 0..1 (no en porcentaje).
- Un valor que no se puede calcular va como `null`, nunca como NaN ni infinito.
"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class Model(BaseModel):
    """Base de todos los esquemas: rechaza campos desconocidos y números no finitos
    (NaN, infinito), tanto en peticiones como en respuestas."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


VariablesChartType = Literal["xbar_r", "xbar_s", "i_mr"]
AttributesChartType = Literal["p", "np", "c", "u"]
ChartType = Literal["xbar_r", "xbar_s", "i_mr", "p", "np", "c", "u"]
Phase = Literal["I", "II"]

# Identificadores de reglas de corrida.
# WE1..WE4: Western Electric. N1..N8: Nelson.
RuleId = Literal[
    "WE1", "WE2", "WE3", "WE4",
    "N1", "N2", "N3", "N4", "N5", "N6", "N7", "N8",
]


class RuleConfig(Model):
    """Reglas de corrida que se evalúan. Por defecto solo un punto fuera de límites."""

    enabled: list[RuleId] = Field(default_factory=lambda: ["WE1"])


class RuleViolation(Model):
    """Señal detectada en un punto de un gráfico."""

    rule: RuleId
    index: int = Field(description="Posición (base 0) del punto donde se completa la señal")
    description: str = Field(description="Explicación en español, lista para mostrar")


class SkippedRule(Model):
    """Regla pedida que no se evaluó en un panel, con el motivo."""

    rule: RuleId
    reason: str


class ExcludedPoint(Model):
    """Punto retirado del cálculo de límites en Fase I por causa asignable."""

    index: int
    label: Optional[str] = None
    cause: str = Field(min_length=1, description="Causa asignable documentada (obligatoria)")


class ChartSeries(Model):
    """Un panel de un gráfico de control (por ejemplo X-barra, o R).

    Los límites van por punto para admitir tamaño de muestra variable (p, u).
    Cuando el límite es constante la lista repite el mismo valor.

    `labels`, `values`, `center`, `ucl`, `lcl` e `indices` tienen la misma longitud.
    Esa longitud puede ser menor que el número de subgrupos: el panel de rango
    móvil no tiene valor para la primera observación. Por eso `indices[k]` dice
    a qué subgrupo (base 0) corresponde `values[k]`. Los índices de `violations`
    y `excluded` son siempre de subgrupo, no de posición en `values`.
    """

    name: Literal["xbar", "r", "s", "i", "mr", "p", "np", "c", "u"]
    title: str
    labels: list[str]
    values: list[float]
    center: list[float]
    ucl: list[float]
    lcl: list[float]
    violations: list[RuleViolation] = []
    excluded: list[int] = Field(default=[], description="Índices excluidos del cálculo de límites")
    indices: list[int] = Field(description="Subgrupo (base 0) de cada elemento de `values`")
    rules_applied: list[RuleId] = Field(default=[], description="Reglas evaluadas en este panel")
    rules_skipped: list[SkippedRule] = Field(
        default=[],
        description="Reglas pedidas que no aplican a este panel (por ejemplo, las de zonas con límites asimétricos)",
    )


class FrozenLimits(Model):
    """Parámetros del proceso estimados en Fase I y congelados para Fase II.

    `params` contiene lo necesario para reconstruir los límites con cualquier n:
    - variables: `mu`, `sigma` (sigma del proceso, no del estadístico)
    - p / np:    `p_bar`
    - c:         `c_bar`
    - u:         `u_bar`
    """

    chart_type: ChartType
    subgroup_size: Optional[int] = Field(default=None, description="n usado en Fase I; null si fue variable")
    sigma_method: Optional[Literal["rbar_d2", "sbar_c4", "mrbar_d2"]] = None
    params: dict[str, float]
    points_used: int = Field(description="Subgrupos que quedaron en el cálculo")
    excluded: list[ExcludedPoint] = []
    limit_width: float = Field(default=3.0, description="L: ancho de los límites en desviaciones estándar")


class Interpretation(Model):
    """Conclusiones preliminares generadas automáticamente (módulo 8)."""

    summary: str = Field(description="Una o dos frases con la conclusión principal")
    findings: list[str] = Field(default=[], description="Hallazgos, uno por elemento")
    warnings: list[str] = Field(default=[], description="Limitaciones y supuestos incumplidos")


class CurvePoint(Model):
    """Punto (x, y) de una curva: OC, AOQ, ATI, ASN."""

    x: float
    y: float


class ErrorResponse(Model):
    """Cuerpo de cualquier respuesta 4xx. `detail` va en español y es mostrable."""

    detail: str
    code: Literal[
        "invalid_data", "insufficient_data", "missing_limits",
        "unsupported_file", "unauthorized",
        "forbidden", "assistant_unavailable",
    ]
