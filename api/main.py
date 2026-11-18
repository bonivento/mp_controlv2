"""Punto de entrada de la API del software CEP (FastAPI).

Vercel detecta la variable `app` de este archivo y la sirve como función
serverless. En local: `uv run uvicorn main:app --reload --port 8000`.

Cada módulo vive en `app/routers/`. Todas las rutas exigen sesión de Supabase
(`app/auth.py`) salvo `/api/health`.
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth import load_local_env

load_local_env()

from app.routers import assistant, assumptions, capability, charts, data, design, reports, sampling  # noqa: E402
from app.routers.errors import install_error_handlers  # noqa: E402

app = FastAPI(
    title="CEP API",
    description="Motor de cálculo de Control Estadístico de Procesos. Sin estado.",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

_origins = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins.split(",") if o.strip()],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["Content-Disposition"],
)

install_error_handlers(app)


@app.get("/api/health")
def health() -> dict:
    """Comprueba que la función arranca y que numpy y scipy cargan."""
    import numpy
    import scipy

    return {"status": "ok", "numpy": numpy.__version__, "scipy": scipy.__version__}


# El orden de montaje fija el orden de las rutas en el OpenAPI.
for module in (data, charts, assumptions, capability, design, sampling, reports, assistant):
    app.include_router(module.router)
