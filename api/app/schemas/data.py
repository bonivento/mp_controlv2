"""Módulo 1. Gestión de datos.

- POST /api/data/parse    (multipart: `file`)  -> ParsedFile
- POST /api/data/summary  (SummaryRequest)     -> SummaryResponse
- POST /api/data/summary/attributes (AttributeSummaryRequest) -> AttributeSummaryResponse

El archivo no se guarda en el servidor: se lee, se devuelve como tabla y el
frontend decide qué columnas usar y lo persiste en Supabase.
"""

from typing import Literal, Optional, Union

from pydantic import Field

from .common import Model

Cell = Union[float, str, None]


class ColumnInfo(Model):
    name: str
    kind: Literal["numeric", "text", "datetime", "empty"]
    missing: int = Field(description="Celdas vacías o no numéricas en una columna numérica")


class ParsedSheet(Model):
    name: str = Field(description="Nombre de la hoja; 'CSV' para archivos .csv")
    columns: list[ColumnInfo]
    rows: list[list[Cell]] = Field(description="Filas en el orden de `columns`")


class ParsedFile(Model):
    filename: str
    sheets: list[ParsedSheet]


class SummaryRequest(Model):
    """Subgrupos ya formados por el frontend. Para datos individuales, n = 1."""

    subgroups: list[list[float]] = Field(min_length=1)
    labels: Optional[list[str]] = None


class SubgroupSummary(Model):
    label: str
    n: int
    mean: float
    range: Optional[float] = Field(description="null si n = 1")
    std: Optional[float] = Field(description="Desviación muestral; null si n = 1")
    min: float
    max: float


class Descriptive(Model):
    """Estadística descriptiva de todas las observaciones juntas."""

    count: int
    mean: float
    std: float
    min: float
    q1: float
    median: float
    q3: float
    max: float
    skewness: Optional[float]
    kurtosis: Optional[float] = Field(description="Exceso de curtosis")


class OutlierFlag(Model):
    """Observación sospechosa. Se marca, no se elimina: decide el usuario."""

    subgroup_index: int
    position: int = Field(description="Posición dentro del subgrupo (base 0)")
    value: float
    reason: str


class SummaryResponse(Model):
    subgroups: list[SubgroupSummary]
    overall: Descriptive
    constant_size: bool
    outliers: list[OutlierFlag] = Field(description="Criterio 1.5·IQR sobre todas las observaciones")


class AttributeSummaryRequest(Model):
    """Datos por atributos ya organizados por subgrupo."""

    counts: list[float] = Field(min_length=1, description="No conformes (p, np) o no conformidades (c, u)")
    sizes: Optional[list[float]] = Field(default=None, description="Tamaño de muestra por subgrupo; null si no aplica (c)")
    labels: Optional[list[str]] = None


class AttributeRow(Model):
    label: str
    count: float
    size: Optional[float]
    rate: Optional[float] = Field(description="count / size; null si no hay tamaño o es 0")


class AttributeSummaryResponse(Model):
    rows: list[AttributeRow]
    subgroups: int
    total_count: float
    total_size: Optional[float]
    overall_rate: Optional[float] = Field(description="total_count / total_size")
    mean_count: float
    min_size: Optional[float]
    max_size: Optional[float]
    constant_size: Optional[bool] = Field(description="null si no se enviaron tamaños")
    warnings: list[str] = Field(default=[], description="Por ejemplo, conteo mayor que el tamaño de muestra")
