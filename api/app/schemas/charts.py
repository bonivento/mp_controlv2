"""Módulos 2 y 3. Gráficos de control por variables y por atributos.

- POST /api/charts/variables         (VariablesChartRequest)   -> ChartResponse
- POST /api/charts/attributes        (AttributesChartRequest)  -> ChartResponse
- POST /api/charts/attributes/recommend (RecommendRequest)     -> RecommendResponse

Fase I y Fase II usan el mismo endpoint:
- Fase I:  `limits` va en null. Los límites se estiman con los datos enviados,
           dejando fuera los puntos de `excluded`. La respuesta trae `limits`
           listo para guardar (congelar).
- Fase II: `limits` es obligatorio (si falta: 422 con code `missing_limits`).
           Los datos se comparan contra esos límites; nunca se recalculan.
"""

from typing import Optional

from pydantic import Field, model_validator

from .common import (
    AttributesChartType,
    ChartSeries,
    ExcludedPoint,
    FrozenLimits,
    Interpretation,
    Model,
    Phase,
    RuleConfig,
    VariablesChartType,
)


def _reject_phase_two_exclusions(request):
    """En Fase II no se depura: los puntos se comparan todos contra los límites."""
    if request.phase == "II" and request.excluded:
        raise ValueError("En Fase II no se excluyen puntos: la exclusión solo aplica al fijar límites en Fase I")
    return request


class VariablesChartRequest(Model):
    chart_type: VariablesChartType
    phase: Phase
    subgroups: list[list[float]] = Field(
        min_length=2,
        description="Un elemento por subgrupo. xbar_r y xbar_s: n >= 2 constante. i_mr: n = 1.",
    )
    labels: Optional[list[str]] = None
    excluded: list[ExcludedPoint] = Field(default=[], description="Solo Fase I")
    limits: Optional[FrozenLimits] = Field(default=None, description="Obligatorio en Fase II")
    limit_width: float = Field(default=3.0, gt=0, description="L; solo se usa en Fase I")
    rules: RuleConfig = RuleConfig()

    @model_validator(mode="after")
    def _no_exclusions_in_phase_two(self):
        return _reject_phase_two_exclusions(self)


class AttributesChartRequest(Model):
    chart_type: AttributesChartType
    phase: Phase
    counts: list[float] = Field(
        min_length=2,
        description="p y np: unidades no conformes. c y u: número de no conformidades.",
    )
    sizes: Optional[list[float]] = Field(
        default=None,
        description="Tamaño de muestra por subgrupo. Obligatorio en p, np y u. "
        "En np debe ser constante. En u puede ser fraccionario (unidades de inspección).",
    )
    labels: Optional[list[str]] = None
    excluded: list[ExcludedPoint] = []
    limits: Optional[FrozenLimits] = None
    limit_width: float = Field(default=3.0, gt=0)
    rules: RuleConfig = RuleConfig()

    @model_validator(mode="after")
    def _no_exclusions_in_phase_two(self):
        return _reject_phase_two_exclusions(self)


class ChartResponse(Model):
    chart_type: str
    phase: Phase
    charts: list[ChartSeries] = Field(
        description="Paneles en orden: variables trae dos (localización, dispersión); atributos uno."
    )
    limits: FrozenLimits = Field(description="Fase I: calculados. Fase II: los mismos que se enviaron.")
    in_control: bool = Field(description="True si ningún punto no excluido tiene señales")
    out_of_control_points: list[int] = Field(description="Índices con al menos una señal, sin repetir")
    interpretation: Interpretation


class RecommendRequest(Model):
    """Datos mínimos para sugerir el gráfico por atributos adecuado."""

    counting: str = Field(
        pattern="^(defectives|defects)$",
        description="defectives: unidades no conformes. defects: no conformidades por unidad.",
    )
    constant_size: bool


class RecommendResponse(Model):
    chart_type: AttributesChartType
    alternatives: list[AttributesChartType]
    justification: str = Field(description="Texto en español que explica la selección")
