"""Módulo 5. Capacidad del proceso.

- POST /api/capability (CapabilityRequest) -> CapabilityResponse

Sigma de corto plazo (within), en orden de prioridad:
1. `limits` (parámetros congelados de Fase I): es lo recomendado.
2. `subgroups` con n >= 2: R-barra/d2 o S-barra/c4 según `sigma_method`.
3. `subgroups` con n = 1: MR-barra/d2.
Sigma de largo plazo (overall): desviación muestral de todas las observaciones.
"""

from typing import Literal, Optional

from pydantic import Field, model_validator

from .assumptions import Histogram
from .common import FrozenLimits, Interpretation, Model


class CapabilityRequest(Model):
    subgroups: list[list[float]] = Field(min_length=2)
    lsl: Optional[float] = None
    usl: Optional[float] = None
    target: Optional[float] = None
    limits: Optional[FrozenLimits] = None
    sigma_method: Optional[Literal["rbar_d2", "sbar_c4", "mrbar_d2"]] = None
    confidence: float = Field(default=0.95, gt=0, lt=1)
    # Resultados de otros módulos, para advertir si no se cumplen los requisitos.
    is_stable: Optional[bool] = Field(default=None, description="Resultado de Fase I, si se conoce")
    is_normal: Optional[bool] = Field(default=None, description="Resultado del módulo 4, si se conoce")

    @model_validator(mode="after")
    def _needs_a_spec(self):
        if self.lsl is None and self.usl is None:
            raise ValueError("Se requiere al menos un límite de especificación (LSL o USL)")
        if self.lsl is not None and self.usl is not None and self.lsl >= self.usl:
            raise ValueError("LSL debe ser menor que USL")
        return self


class IndexValue(Model):
    """Índice con su intervalo de confianza. `value` es null si no aplica
    (por ejemplo Cp con una sola especificación)."""

    value: Optional[float]
    lower: Optional[float] = None
    upper: Optional[float] = None


class NonConforming(Model):
    """Fracción fuera de especificación, en escala 0..1, y su equivalente en PPM."""

    below_lsl: Optional[float]
    above_usl: Optional[float]
    total: float
    ppm: float


class CapabilityResponse(Model):
    n: int
    mean: float
    sigma_within: float
    sigma_overall: float
    sigma_method: Literal["rbar_d2", "sbar_c4", "mrbar_d2", "frozen_limits"]
    # Capacidad potencial (corto plazo)
    cp: IndexValue
    cpl: IndexValue
    cpu: IndexValue
    cpk: IndexValue
    # Desempeño (largo plazo)
    pp: IndexValue
    ppl: IndexValue
    ppu: IndexValue
    ppk: IndexValue
    cpm: IndexValue = Field(description="Solo si se envía `target`")
    expected_within: NonConforming = Field(description="Modelo normal con sigma within")
    expected_overall: NonConforming = Field(description="Modelo normal con sigma overall")
    observed: NonConforming = Field(description="Conteo directo sobre los datos")
    histogram: Histogram
    verdict: Literal["inadequate", "marginal", "adequate", "excellent"] = Field(
        description="Según Cpk: <1, 1 a 1.33, 1.33 a 1.67, >=1.67"
    )
    interpretation: Interpretation
