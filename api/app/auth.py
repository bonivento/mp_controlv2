"""Autenticación: verifica el JWT de Supabase del encabezado `Authorization: Bearer`.

Las claves públicas se leen de `{SUPABASE_URL}/auth/v1/.well-known/jwks.json` y
se guardan en memoria. Se verifican firma (ES256 o RS256), expiración,
audiencia `authenticated` y emisor `{SUPABASE_URL}/auth/v1`.

`AUTH_DISABLED=1` desactiva la verificación solo para desarrollo local.
Se ignora cuando `VERCEL_ENV=production` para que nunca quede activa en
producción por un descuido.
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any, Optional

import jwt
from fastapi import Request

AUDIENCE = "authenticated"
ALGORITHMS = ["ES256", "RS256"]
JWKS_TTL_SECONDS = 3600
JWKS_MIN_REFETCH_SECONDS = 30  # evita golpear a Supabase si llegan kid desconocidos


class AuthError(Exception):
    """Sesión ausente o inválida. Se traduce a 401 con `ErrorResponse`."""

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


# --- Variables de entorno ----------------------------------------------------
def load_env_file(path: Path) -> None:
    """Cargador mínimo de `KEY=VALUE`. No pisa variables ya definidas."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].strip()
        if key and key not in os.environ:
            os.environ[key] = value


def load_local_env() -> None:
    """Carga `api/.env.local` si existe (en Vercel no existe: se usan sus variables)."""
    load_env_file(Path(__file__).resolve().parent.parent / ".env.local")


def auth_disabled() -> bool:
    if os.environ.get("VERCEL_ENV") == "production":
        return False
    return os.environ.get("AUTH_DISABLED", "").strip().lower() in ("1", "true", "yes")


def supabase_url() -> str:
    return os.environ.get("SUPABASE_URL", "").strip().rstrip("/")


# --- Claves públicas ---------------------------------------------------------
def fetch_jwks(url: str) -> dict[str, Any]:
    """Descarga el JWKS. Aislada para poder sustituirla en las pruebas."""
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310 (URL de configuración)
        return json.loads(response.read().decode("utf-8"))


class _KeyCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._keys: dict[str, Any] = {}
        self._url: Optional[str] = None
        self._fetched_at = 0.0

    def clear(self) -> None:
        with self._lock:
            self._keys, self._url, self._fetched_at = {}, None, 0.0

    def get(self, kid: str, url: str) -> Any:
        with self._lock:
            now = time.monotonic()
            stale = self._url != url or now - self._fetched_at > JWKS_TTL_SECONDS
            unknown = kid not in self._keys
            can_refetch = now - self._fetched_at > JWKS_MIN_REFETCH_SECONDS or self._url != url
            if (stale or unknown) and can_refetch:
                self._refresh(url, now)
            key = self._keys.get(kid)
        if key is None:
            raise AuthError("La clave con la que se firmó la sesión no es reconocida.")
        return key

    def _refresh(self, url: str, now: float) -> None:
        try:
            document = fetch_jwks(url)
        except Exception as exc:  # red caída, JSON inválido, etc.
            self._fetched_at = now  # no reintentar de inmediato
            if not self._keys:
                raise AuthError("No se pudieron obtener las claves para verificar la sesión.") from exc
            return
        keys: dict[str, Any] = {}
        for jwk in document.get("keys", []):
            kid = jwk.get("kid")
            if not kid:
                continue
            try:
                keys[kid] = jwt.PyJWK(jwk).key
            except Exception:
                continue
        self._keys, self._url, self._fetched_at = keys, url, now


key_cache = _KeyCache()


def verify_token(token: str) -> dict[str, Any]:
    base = supabase_url()
    if not base:
        raise AuthError("El servidor no tiene configurado SUPABASE_URL: no se puede verificar la sesión.")
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise AuthError("El token de sesión no es válido.") from exc
    kid = header.get("kid")
    if not kid or header.get("alg") not in ALGORITHMS:
        raise AuthError("El token de sesión no es válido.")
    key = key_cache.get(kid, f"{base}/auth/v1/.well-known/jwks.json")
    try:
        return jwt.decode(
            token,
            key,
            algorithms=ALGORITHMS,
            audience=AUDIENCE,
            issuer=f"{base}/auth/v1",
            options={"require": ["exp", "aud", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("La sesión expiró. Inicie sesión de nuevo.") from exc
    except jwt.PyJWTError as exc:
        raise AuthError("El token de sesión no es válido.") from exc


def require_auth(request: Request) -> Optional[dict[str, Any]]:
    """Dependencia de FastAPI. No declara parámetros para no alterar el OpenAPI."""
    if auth_disabled():
        return None
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise AuthError("Falta la sesión: envíe el encabezado Authorization con el token de Supabase.")
    return verify_token(token.strip())
