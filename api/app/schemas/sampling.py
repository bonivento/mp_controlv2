"""Módulo 7. Muestreo de aceptación por atributos.

- POST /api/sampling/single/design    (SingleDesignRequest)   -> SinglePlanResponse
- POST /api/sampling/single/evaluate  (SingleEvaluateRequest) -> SinglePlanResponse
- POST /api/sampling/double/evaluate  (DoubleEvaluateRequest) -> DoublePlanResponse

Notación:
- AQL (p1): nivel de calidad aceptable; se acepta con probabilidad >= 1 - alpha.
- LTPD (p2): calidad límite; se acepta con probabilidad <= beta.
- AOQ: calidad promedio de salida con inspección rectificadora. AOQL: su máximo.
- ATI: inspección total promedio por lote. ASN: tamaño promedio de muestra.
"""

from typing import Literal, Optional

from pydantic import Field

from .common import CurvePoint, Interpretation, Model

Distribution = Literal["binomial", "poisson", "hypergeometric"]


class PlanRef(Model):
    """Plan simple (n, c) con el que se quiere comparar, por ejemplo el de un nomograma."""

    n: int = Field(ge=1)
    c: int = Field(ge=0)


class SingleDesignRequest(Model):
    aql: float = Field(gt=0, lt=1)
    alpha: float = Field(default=0.05, gt=0, lt=1, description="Riesgo del productor")
    ltpd: float = Field(gt=0, lt=1)
    beta: float = Field(default=0.10, gt=0, lt=1, description="Riesgo del consumidor")
    lot_size: Optional[int] = Field(default=None, ge=2, description="N; obligatorio con hipergeométrica y para ATI")
    distribution: Distribution = "binomial"
    reference_plan: Optional[PlanRef] = Field(default=None, description="Plan de referencia para comparar")


class SingleEvaluateRequest(Model):
    n: int = Field(ge=1)
    c: int = Field(ge=0)
    lot_size: Optional[int] = Field(default=None, ge=2)
    distribution: Distribution = "binomial"
    aql: Optional[float] = Field(default=None, gt=0, lt=1)
    ltpd: Optional[float] = Field(default=None, gt=0, lt=1)


class SinglePlanResponse(Model):
    n: int
    c: int
    distribution: Distribution
    alpha_actual: Optional[float] = Field(description="1 - Pa(AQL); null si no se envió AQL")
    beta_actual: Optional[float] = Field(description="Pa(LTPD); null si no se envió LTPD")
    oc_curve: list[CurvePoint] = Field(description="x: fracción defectuosa del lote, y: Pa")
    aoq_curve: list[CurvePoint]
    aoql: float
    aoql_at: float = Field(description="Fracción defectuosa donde ocurre el AOQL")
    ati_curve: Optional[list[CurvePoint]] = Field(description="null si no se envió lot_size")
    interpretation: Interpretation


class DoubleEvaluateRequest(Model):
    """Plan doble: se acepta en la primera muestra si d1 <= c1, se rechaza si
    d1 >= r1; en otro caso se toma la segunda y se acepta si d1 + d2 <= c2."""

    n1: int = Field(ge=1)
    c1: int = Field(ge=0)
    r1: int = Field(ge=1, description="Número de rechazo de la primera muestra: c1 < r1 <= c2 + 1; lo habitual es r1 = c2 + 1")
    n2: int = Field(ge=1)
    c2: int = Field(ge=0)
    lot_size: Optional[int] = Field(default=None, ge=2)
    aql: Optional[float] = Field(default=None, gt=0, lt=1)
    ltpd: Optional[float] = Field(default=None, gt=0, lt=1)


class DoublePlanResponse(Model):
    oc_curve: list[CurvePoint]
    asn_curve: list[CurvePoint] = Field(description="Sin inspección truncada")
    first_sample_accept_curve: list[CurvePoint]
    alpha_actual: Optional[float]
    beta_actual: Optional[float]
    aoq_curve: list[CurvePoint]
    aoql: float
    aoql_at: Optional[float] = Field(default=None, description="Fracción defectuosa donde ocurre el AOQL")
    ati_curve: Optional[list[CurvePoint]]
    interpretation: Interpretation
