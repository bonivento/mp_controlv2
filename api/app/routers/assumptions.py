"""Módulo 4. Supuestos."""

from dataclasses import asdict

from fastapi import APIRouter, Depends

from app.auth import require_auth
from app.schemas import assumptions
from app.spc import assumptions as spc

router = APIRouter(dependencies=[Depends(require_auth)])


@router.post("/api/assumptions", response_model=assumptions.AssumptionsResponse, tags=["supuestos"])
def check_assumptions(body: assumptions.AssumptionsRequest):
    result = spc.analyze_assumptions(body.values, body.alpha, body.max_lag, body.histogram_bins)
    return asdict(result)
