import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from app import auth

BASE = "https://proyecto-de-prueba.supabase.co"
PROTECTED = "/api/charts/attributes/recommend"
BODY = {"counting": "defects", "constant_size": True}


def _keypair(kid):
    private = ec.generate_private_key(ec.SECP256R1())
    jwk = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(private.public_key()))
    jwk.update({"kid": kid, "alg": "ES256", "use": "sig"})
    return private, jwk


def _token(private, kid="k1", **overrides):
    claims = {"sub": "u1", "aud": "authenticated", "iss": f"{BASE}/auth/v1", "exp": int(time.time()) + 600}
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, private, algorithm="ES256", headers={"kid": kid})


@pytest.fixture()
def jwks(monkeypatch):
    private, jwk = _keypair("k1")
    calls = []

    def fake_fetch(url):
        calls.append(url)
        return {"keys": [jwk]}

    monkeypatch.setattr(auth, "fetch_jwks", fake_fetch)
    auth.key_cache.clear()
    yield private, calls
    auth.key_cache.clear()


def _post(client, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.post(PROTECTED, json=BODY, headers=headers)


def test_health_is_public(strict_client):
    assert strict_client.get("/api/health").status_code == 200


@pytest.mark.parametrize("route", [
    "/api/data/parse", "/api/data/summary", "/api/data/summary/attributes", "/api/charts/variables",
    "/api/charts/attributes", "/api/charts/attributes/recommend", "/api/assumptions", "/api/capability",
    "/api/design/arl", "/api/design/compare", "/api/sampling/single/design", "/api/sampling/single/evaluate",
    "/api/sampling/double/evaluate", "/api/reports/excel",
])
def test_every_route_rejects_missing_token(strict_client, route):
    r = strict_client.post(route, json={})
    assert r.status_code == 401
    assert r.json()["code"] == "unauthorized"
    assert r.json()["detail"]


def test_valid_token_is_accepted_and_keys_are_cached(strict_client, jwks):
    private, calls = jwks
    assert _post(strict_client, _token(private)).status_code == 200
    assert _post(strict_client, _token(private)).status_code == 200
    assert calls == [f"{BASE}/auth/v1/.well-known/jwks.json"]


def test_expired_token(strict_client, jwks):
    private, _ = jwks
    r = _post(strict_client, _token(private, exp=int(time.time()) - 10))
    assert r.status_code == 401 and r.json()["code"] == "unauthorized"


def test_wrong_audience(strict_client, jwks):
    private, _ = jwks
    assert _post(strict_client, _token(private, aud="anon")).status_code == 401


def test_wrong_issuer(strict_client, jwks):
    private, _ = jwks
    assert _post(strict_client, _token(private, iss="https://otro.supabase.co/auth/v1")).status_code == 401


def test_token_signed_with_unknown_key(strict_client, jwks):
    other, _ = _keypair("k1")
    assert _post(strict_client, _token(other)).status_code == 401


def test_unknown_kid(strict_client, jwks):
    private, _ = jwks
    assert _post(strict_client, _token(private, kid="otro")).status_code == 401


def test_garbage_token_and_wrong_scheme(strict_client, jwks):
    assert _post(strict_client, "no-es-un-jwt").status_code == 401
    r = strict_client.post(PROTECTED, json=BODY, headers={"Authorization": "Basic abc"})
    assert r.status_code == 401


def test_jwks_unreachable_is_401(strict_client, monkeypatch):
    def boom(url):
        raise OSError("sin red")

    monkeypatch.setattr(auth, "fetch_jwks", boom)
    auth.key_cache.clear()
    private, _ = _keypair("k1")
    assert _post(strict_client, _token(private)).status_code == 401


def test_auth_disabled_flag(client):
    assert client.post(PROTECTED, json=BODY).status_code == 200


def test_auth_disabled_is_ignored_in_production(strict_client, monkeypatch):
    monkeypatch.setenv("AUTH_DISABLED", "1")
    monkeypatch.setenv("VERCEL_ENV", "production")
    assert strict_client.post(PROTECTED, json=BODY).status_code == 401


def test_env_file_loader(tmp_path, monkeypatch):
    f = tmp_path / ".env.local"
    f.write_text('# c\nA_TEST_VAR="hola"\nB_TEST_VAR=dos # nota\nexport C_TEST_VAR=3\n')
    monkeypatch.setenv("C_TEST_VAR", "previa")
    for k in ("A_TEST_VAR", "B_TEST_VAR"):
        monkeypatch.delenv(k, raising=False)
    auth.load_env_file(f)
    import os

    assert os.environ["A_TEST_VAR"] == "hola"
    assert os.environ["B_TEST_VAR"] == "dos"
    assert os.environ["C_TEST_VAR"] == "previa"
    for k in ("A_TEST_VAR", "B_TEST_VAR"):
        monkeypatch.delenv(k, raising=False)
