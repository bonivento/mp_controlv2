"""Fixtures de las pruebas de routers. Sin red: la autenticación se prueba con claves generadas aquí."""

import os

import pytest
from fastapi.testclient import TestClient

from main import app

# `tests/test_contract.py` (de la sesión principal) llama a la API sin token. Como pytest importa este
# conftest durante la recolección, esto lo deja funcionando en la corrida completa. Las pruebas de
# autenticación quitan la variable de forma explícita (fixture `strict_client`).
os.environ.setdefault("AUTH_DISABLED", "1")


@pytest.fixture()
def client(monkeypatch):
    """Cliente con la autenticación desactivada (como en desarrollo local)."""
    monkeypatch.setenv("AUTH_DISABLED", "1")
    monkeypatch.delenv("VERCEL_ENV", raising=False)
    return TestClient(app)


@pytest.fixture()
def strict_client(monkeypatch):
    """Cliente con la autenticación activa."""
    monkeypatch.delenv("AUTH_DISABLED", raising=False)
    monkeypatch.delenv("VERCEL_ENV", raising=False)
    monkeypatch.setenv("SUPABASE_URL", "https://proyecto-de-prueba.supabase.co")
    return TestClient(app)
