"""Módulo 8. Reportes."""

import re
import unicodedata

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.auth import require_auth
from app.excel_report import XLSX_MEDIA_TYPE, build_workbook
from app.schemas import reports

router = APIRouter(dependencies=[Depends(require_auth)])


def _filename(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^A-Za-z0-9]+", "_", ascii_name).strip("_")[:60] or "estudio"
    return f"reporte_{slug}.xlsx"


@router.post("/api/reports/excel", response_class=Response, tags=["reportes"])
def excel_report(body: reports.ExcelReportRequest):
    content = build_workbook(body.study.model_dump(), [s.model_dump() for s in body.sections])
    return Response(
        content=content,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{_filename(body.study.name)}"'},
    )
