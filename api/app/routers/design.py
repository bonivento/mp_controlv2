"""Módulo 6. Diseño de gráficos (ARL / ATS)."""

from dataclasses import asdict

from fastapi import APIRouter, Depends

from app.auth import require_auth
from app.schemas import design
from app.spc import design as spc

router = APIRouter(dependencies=[Depends(require_auth)])


@router.post("/api/design/arl", response_model=design.ArlResponse, tags=["diseno"])
def arl(body: design.ArlRequest):
    result = spc.compute_arl(
        body.chart, n=body.n, limit_width=body.limit_width, sampling_interval=body.sampling_interval,
        shifts=body.shifts, p0=body.p0, p1=body.p1, c0=body.c0, c1=body.c1,
        rules=body.rules.enabled, max_runs=body.max_runs, max_length=body.max_length, seed=body.seed,
    )
    return asdict(result)


@router.post("/api/design/compare", response_model=design.CompareResponse, tags=["diseno"])
def compare_designs(body: design.CompareRequest):
    result = spc.compare_designs(
        body.n_values, limit_widths=body.limit_widths, sampling_intervals=body.sampling_intervals, shift=body.shift,
    )
    return asdict(result)
