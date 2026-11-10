"""Módulo 8. Reportes.

- POST /api/reports/excel (ExcelReportRequest) -> archivo .xlsx (binario)

El reporte en PDF no pasa por el backend: es la página `/estudios/[id]/reporte`
del frontend con estilos de impresión. Las conclusiones preliminares llegan en
el campo `interpretation` de cada respuesta de análisis.
"""

from typing import Any, Literal, Optional

from pydantic import Field

from .common import Model

Module = Literal["data", "variables", "attributes", "assumptions", "capability", "design", "sampling"]


class StudyInfo(Model):
    name: str
    company: Optional[str] = None
    process: Optional[str] = None
    product: Optional[str] = None
    characteristic: Optional[str] = None
    unit: Optional[str] = None
    lsl: Optional[float] = None
    usl: Optional[float] = None
    target: Optional[float] = None
    analyst: Optional[str] = None


class ReportSection(Model):
    """Un análisis guardado. `result` es la respuesta del endpoint del módulo,
    tal como la devolvió la API y como quedó guardada en `analyses.result`."""

    module: Module
    title: str
    created_at: Optional[str] = None
    result: dict[str, Any]


class ExcelReportRequest(Model):
    study: StudyInfo
    sections: list[ReportSection] = Field(min_length=1)
