"""Módulo 4. Validación de supuestos.

- POST /api/assumptions (AssumptionsRequest) -> AssumptionsResponse

Las señales de patrones no aleatorios (reglas de corrida) se piden en los
endpoints de gráficos con `rules`; aquí van normalidad e independencia.
"""

from typing import Optional

from pydantic import Field

from .common import Interpretation, Model
from .data import Descriptive


class AssumptionsRequest(Model):
    values: list[float] = Field(min_length=8, description="Observaciones individuales en orden temporal")
    alpha: float = Field(default=0.05, gt=0, lt=1)
    max_lag: Optional[int] = Field(default=None, ge=1, description="Por defecto min(20, n/4)")
    histogram_bins: Optional[int] = Field(default=None, ge=3, description="Por defecto regla de Sturges")


class TestResult(Model):
    """Resultado de una prueba de hipótesis."""

    name: str = Field(description="Shapiro-Wilk, Anderson-Darling, Ljung-Box, Rachas")
    null_hypothesis: str
    statistic: float
    p_value: Optional[float] = Field(description="null cuando la prueba solo da valor crítico")
    critical_value: Optional[float] = None
    reject: bool = Field(description="True si se rechaza H0 al nivel alpha")
    conclusion: str


class QQPoint(Model):
    theoretical: float
    observed: float


class Histogram(Model):
    edges: list[float] = Field(description="k + 1 bordes")
    counts: list[int] = Field(description="k frecuencias")
    normal_curve_x: list[float]
    normal_curve_y: list[float] = Field(description="Densidad normal ajustada, en escala de frecuencia")


class Autocorrelation(Model):
    lags: list[int]
    values: list[float]
    band: float = Field(description="Banda de significancia ±z/√n")
    significant_lags: list[int]


class AssumptionsResponse(Model):
    descriptive: Descriptive
    normality: list[TestResult]
    is_normal: bool = Field(description="True si ninguna prueba de normalidad rechaza")
    qq: list[QQPoint]
    histogram: Histogram
    autocorrelation: Autocorrelation
    independence: list[TestResult]
    is_independent: bool
    interpretation: Interpretation
