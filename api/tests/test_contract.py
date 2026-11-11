"""Pruebas del contrato: la app arranca y expone todas las rutas acordadas."""

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

EXPECTED_PATHS = {
    "/api/health",
    "/api/data/parse",
    "/api/data/summary",
    "/api/data/summary/attributes",
    "/api/charts/variables",
    "/api/charts/attributes",
    "/api/charts/attributes/recommend",
    "/api/assumptions",
    "/api/capability",
    "/api/design/arl",
    "/api/design/compare",
    "/api/sampling/single/design",
    "/api/sampling/single/evaluate",
    "/api/sampling/double/evaluate",
    "/api/reports/excel",
}


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_openapi_exposes_every_contract_path():
    paths = set(client.get("/api/openapi.json").json()["paths"])
    assert EXPECTED_PATHS <= paths


def test_capability_requires_a_specification_limit():
    response = client.post("/api/capability", json={"subgroups": [[1, 2], [2, 3]]})
    assert response.status_code == 422
