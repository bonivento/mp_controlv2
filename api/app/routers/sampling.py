"""Módulo 7. Muestreo de aceptación."""

from dataclasses import asdict

from fastapi import APIRouter, Depends

from app.auth import require_auth
from app.schemas import sampling
from app.spc import sampling as spc

router = APIRouter(dependencies=[Depends(require_auth)])


@router.post("/api/sampling/single/design", response_model=sampling.SinglePlanResponse, tags=["muestreo"])
def design_single_plan(body: sampling.SingleDesignRequest):
    ref = (body.reference_plan.n, body.reference_plan.c) if body.reference_plan else None
    result = spc.design_single_plan(
        body.aql, body.ltpd, alpha=body.alpha, beta=body.beta, lot_size=body.lot_size,
        distribution=body.distribution, reference_plan=ref,
    )
    return asdict(result)


@router.post("/api/sampling/single/evaluate", response_model=sampling.SinglePlanResponse, tags=["muestreo"])
def evaluate_single_plan(body: sampling.SingleEvaluateRequest):
    result = spc.evaluate_single_plan(
        body.n, body.c, lot_size=body.lot_size, distribution=body.distribution, aql=body.aql, ltpd=body.ltpd,
    )
    return asdict(result)


@router.post("/api/sampling/double/evaluate", response_model=sampling.DoublePlanResponse, tags=["muestreo"])
def evaluate_double_plan(body: sampling.DoubleEvaluateRequest):
    result = spc.evaluate_double_plan(
        body.n1, body.c1, body.r1, body.n2, body.c2, lot_size=body.lot_size, aql=body.aql, ltpd=body.ltpd,
    )
    return asdict(result)
