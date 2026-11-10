"""Módulo 6. Diseño de gráficos: ARL0, ARL1 y ATS.

- POST /api/design/arl      (ArlRequest)     -> ArlResponse
- POST /api/design/compare  (CompareRequest) -> CompareResponse

Definiciones:
- ARL0: número promedio de muestras hasta una falsa alarma (proceso en control).
- ARL1: número promedio de muestras hasta detectar un desplazamiento dado.
- ATS = ARL · h, con h el intervalo entre muestras (en horas).
- Carga muestral = n / h (unidades inspeccionadas por hora).

Método:
- `exact`: fórmula cerrada. Solo regla de un punto fuera de límites (WE1).
- `simulation`: Monte Carlo, cuando se activan reglas suplementarias.
  Acotada por `max_runs` y `max_length` para no exceder el tiempo de Vercel.
"""

from typing import Literal, Optional

from pydantic import Field

from .common import CurvePoint, Interpretation, Model, RuleConfig


class ArlRequest(Model):
    chart: Literal["xbar", "individuals", "p", "c"]
    n: int = Field(default=1, ge=1, description="Tamaño de subgrupo (xbar, p). Ignorado en individuals y c")
    limit_width: float = Field(default=3.0, gt=0, description="L")
    sampling_interval: float = Field(default=1.0, gt=0, description="h, en horas")
    # xbar / individuals: desplazamientos de la media en múltiplos de sigma del proceso
    shifts: list[float] = Field(default=[0.5, 1.0, 1.5, 2.0, 3.0])
    # p: fracción en control y fracciones desplazadas
    p0: Optional[float] = Field(default=None, gt=0, lt=1)
    p1: Optional[list[float]] = Field(default=None, description="Si es null: 1.5, 2, 2.5 y 3 veces p0")
    # c: media en control y medias desplazadas
    c0: Optional[float] = Field(default=None, gt=0)
    c1: Optional[list[float]] = Field(default=None, description="Si es null: 1.5, 2, 2.5 y 3 veces c0")
    rules: RuleConfig = RuleConfig()
    max_runs: int = Field(default=5000, ge=100, le=20000)
    max_length: int = Field(default=20000, ge=100, le=100000)
    seed: Optional[int] = Field(default=12345, description="Semilla fija: resultados reproducibles")


class ArlRow(Model):
    """Desempeño del gráfico para un estado fuera de control."""

    shift: float = Field(description="delta en sigmas (xbar, individuals), o p1, o c1")
    beta: Optional[float] = Field(description="Probabilidad de no detectar en una muestra; null en simulación")
    arl1: float
    ats1: float = Field(description="Horas promedio hasta detectar")
    units_to_detect: float = Field(description="Unidades inspeccionadas hasta detectar = ARL1 · n")
    std_error: Optional[float] = Field(default=None, description="Error estándar del ARL; solo en simulación")


class ArlResponse(Model):
    method: Literal["exact", "simulation"]
    alpha: Optional[float] = Field(description="Probabilidad de falsa alarma por muestra")
    arl0: float
    arl0_std_error: Optional[float] = Field(default=None, description="Error estándar del ARL0; solo en simulación")
    ats0: float
    sampling_load: float = Field(description="n / h, unidades por hora")
    rows: list[ArlRow]
    oc_curve: list[CurvePoint] = Field(
        description="x: desplazamiento, y: beta. En simulación es la curva de la regla de un punto "
        "fuera de límites sola, como referencia; se advierte en la interpretación."
    )
    arl_curve: list[CurvePoint] = Field(description="x: desplazamiento, y: ARL")
    interpretation: Interpretation


class CompareRequest(Model):
    """Compara diseños alternativos de un gráfico X-barra para un desplazamiento."""

    n_values: list[int] = Field(min_length=1)
    limit_widths: list[float] = Field(default=[3.0])
    sampling_intervals: list[float] = Field(default=[1.0])
    shift: float = Field(default=1.0, description="Desplazamiento que interesa detectar, en sigmas")


class CompareRow(Model):
    n: int
    limit_width: float
    sampling_interval: float
    arl0: float
    ats0: float
    arl1: float
    ats1: float
    sampling_load: float


class CompareResponse(Model):
    shift: float
    rows: list[CompareRow]
    interpretation: Interpretation
