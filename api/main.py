"""Punto de entrada de la API del software CEP (FastAPI).

Vercel detecta la variable `app` de este archivo y la sirve como función
serverless. En local: `uv run uvicorn main:app --reload --port 8000`.

En la Ola 0 las rutas son solo el contrato: declaran entrada y salida y
responden 501. El agente `backend-api` reemplaza cada una por su router real
en `app/routers/` durante la Ola 2.
"""

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import Response

from app.schemas import assumptions, capability, charts, data, design, reports, sampling

app = FastAPI(
    title="CEP API",
    description="Motor de cálculo de Control Estadístico de Procesos. Sin estado.",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)


def _pending():
    raise HTTPException(status_code=501, detail="Pendiente de implementar")


@app.get("/api/health")
def health() -> dict:
    """Comprueba que la función arranca y que numpy y scipy cargan."""
    import numpy
    import scipy

    return {"status": "ok", "numpy": numpy.__version__, "scipy": scipy.__version__}


# --- Módulo 1: datos ---------------------------------------------------------
@app.post("/api/data/parse", response_model=data.ParsedFile, tags=["datos"])
def parse_file(file: UploadFile = File(...)):
    _pending()


@app.post("/api/data/summary", response_model=data.SummaryResponse, tags=["datos"])
def summary(body: data.SummaryRequest):
    _pending()


# --- Módulos 2 y 3: gráficos de control --------------------------------------
@app.post("/api/charts/variables", response_model=charts.ChartResponse, tags=["graficos"])
def variables_chart(body: charts.VariablesChartRequest):
    _pending()


@app.post("/api/charts/attributes", response_model=charts.ChartResponse, tags=["graficos"])
def attributes_chart(body: charts.AttributesChartRequest):
    _pending()


@app.post("/api/charts/attributes/recommend", response_model=charts.RecommendResponse, tags=["graficos"])
def recommend_chart(body: charts.RecommendRequest):
    _pending()


# --- Módulo 4: supuestos -----------------------------------------------------
@app.post("/api/assumptions", response_model=assumptions.AssumptionsResponse, tags=["supuestos"])
def check_assumptions(body: assumptions.AssumptionsRequest):
    _pending()


# --- Módulo 5: capacidad -----------------------------------------------------
@app.post("/api/capability", response_model=capability.CapabilityResponse, tags=["capacidad"])
def process_capability(body: capability.CapabilityRequest):
    _pending()


# --- Módulo 6: diseño (ARL / ATS) --------------------------------------------
@app.post("/api/design/arl", response_model=design.ArlResponse, tags=["diseno"])
def arl(body: design.ArlRequest):
    _pending()


@app.post("/api/design/compare", response_model=design.CompareResponse, tags=["diseno"])
def compare_designs(body: design.CompareRequest):
    _pending()


# --- Módulo 7: muestreo de aceptación ----------------------------------------
@app.post("/api/sampling/single/design", response_model=sampling.SinglePlanResponse, tags=["muestreo"])
def design_single_plan(body: sampling.SingleDesignRequest):
    _pending()


@app.post("/api/sampling/single/evaluate", response_model=sampling.SinglePlanResponse, tags=["muestreo"])
def evaluate_single_plan(body: sampling.SingleEvaluateRequest):
    _pending()


@app.post("/api/sampling/double/evaluate", response_model=sampling.DoublePlanResponse, tags=["muestreo"])
def evaluate_double_plan(body: sampling.DoubleEvaluateRequest):
    _pending()


# --- Módulo 8: reportes ------------------------------------------------------
@app.post("/api/reports/excel", response_class=Response, tags=["reportes"])
def excel_report(body: reports.ExcelReportRequest):
    _pending()
