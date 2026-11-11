"""Módulos 2 y 3. Gráficos de control."""

from dataclasses import asdict

from fastapi import APIRouter, Depends

from app.auth import require_auth
from app.schemas import charts
from app.spc import attributes, interpretation, phases
from app.spc.constants import SPCInputError

router = APIRouter(dependencies=[Depends(require_auth)])


def _respond(result, rules):
    payload = result.to_contract()
    payload["interpretation"] = asdict(interpretation.interpret_chart_result(result, rules=rules.enabled))
    return payload


def _run(body, data, sizes):
    if body.phase == "I":
        result = phases.phase_one(
            body.chart_type, data, sizes,
            excluded=body.excluded, limit_width=body.limit_width, rules=body.rules, labels=body.labels,
        )
    else:
        if body.limits is None:
            raise SPCInputError(
                "La Fase II necesita los límites congelados de la Fase I: envíelos en `limits`.",
                "missing_limits",
            )
        result = phases.phase_two(body.chart_type, data, body.limits, sizes, rules=body.rules, labels=body.labels)
    return _respond(result, body.rules)


@router.post("/api/charts/variables", response_model=charts.ChartResponse, tags=["graficos"])
def variables_chart(body: charts.VariablesChartRequest):
    return _run(body, body.subgroups, None)


@router.post("/api/charts/attributes", response_model=charts.ChartResponse, tags=["graficos"])
def attributes_chart(body: charts.AttributesChartRequest):
    return _run(body, body.counts, body.sizes)


@router.post("/api/charts/attributes/recommend", response_model=charts.RecommendResponse, tags=["graficos"])
def recommend_chart(body: charts.RecommendRequest):
    return asdict(attributes.recommend_chart(body.counting, body.constant_size))
