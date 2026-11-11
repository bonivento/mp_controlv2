"""Módulo 5. Capacidad."""

from dataclasses import asdict

from fastapi import APIRouter, Depends

from app.auth import require_auth
from app.schemas import capability
from app.spc import capability as spc

router = APIRouter(dependencies=[Depends(require_auth)])


@router.post("/api/capability", response_model=capability.CapabilityResponse, tags=["capacidad"])
def process_capability(body: capability.CapabilityRequest):
    result = spc.analyze_capability(
        body.subgroups, lsl=body.lsl, usl=body.usl, target=body.target, limits=body.limits,
        sigma_method=body.sigma_method, confidence=body.confidence,
        is_stable=body.is_stable, is_normal=body.is_normal,
    )
    return asdict(result)
