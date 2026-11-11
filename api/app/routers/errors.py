"""Conversión de excepciones a `ErrorResponse` (detail en español + code)."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.auth import AuthError
from app.spc.constants import SPCInputError

_TYPE_MESSAGES = {
    "missing": "falta este dato",
    "extra_forbidden": "campo no reconocido",
    "string_type": "debe ser texto",
    "int_type": "debe ser un número entero",
    "int_parsing": "debe ser un número entero",
    "int_from_float": "debe ser un número entero",
    "float_type": "debe ser un número",
    "float_parsing": "debe ser un número",
    "bool_type": "debe ser verdadero o falso",
    "list_type": "debe ser una lista",
    "dict_type": "debe ser un objeto",
    "json_invalid": "el cuerpo no es JSON válido",
    "string_pattern_mismatch": "valor no permitido",
    "literal_error": "valor no permitido",
    "finite_number": "debe ser un número finito",
}


def _location(loc: tuple) -> str:
    parts = [str(p) for p in loc if p not in ("body", "query")]
    return ".".join(parts)


def _message(err: dict) -> str:
    kind = err.get("type", "")
    ctx = err.get("ctx") or {}
    if kind in _TYPE_MESSAGES:
        text = _TYPE_MESSAGES[kind]
        if kind == "literal_error" and "expected" in ctx:
            text += f" (opciones: {ctx['expected']})"
        return text
    limits = {
        "greater_than": "debe ser mayor que {gt}",
        "greater_than_equal": "debe ser mayor o igual que {ge}",
        "less_than": "debe ser menor que {lt}",
        "less_than_equal": "debe ser menor o igual que {le}",
        "too_short": "debe tener al menos {min_length} elementos",
        "too_long": "debe tener como máximo {max_length} elementos",
        "string_too_short": "debe tener al menos {min_length} caracteres",
    }
    if kind in limits:
        try:
            return limits[kind].format(**ctx)
        except KeyError:
            return "fuera del rango permitido"
    msg = str(err.get("msg", "dato inválido"))
    return msg.removeprefix("Value error, ")


def validation_detail(errors: list[dict]) -> str:
    parts = []
    for err in errors[:5]:
        where = _location(tuple(err.get("loc", ())))
        text = _message(err)
        parts.append(f"{where}: {text}" if where else text)
    more = len(errors) - 5
    detail = "Datos inválidos. " + "; ".join(parts) + "."
    if more > 0:
        detail += f" (y {more} problema{'s' if more > 1 else ''} más)"
    return detail


def _error(status: int, detail: str, code: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": detail, "code": code})


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AuthError)
    async def _auth(_: Request, exc: AuthError):
        return JSONResponse(
            status_code=401,
            content={"detail": exc.detail, "code": "unauthorized"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        return _error(422, validation_detail(exc.errors()), "invalid_data")

    @app.exception_handler(SPCInputError)
    async def _spc(_: Request, exc: SPCInputError):
        return _error(422, str(exc), exc.code)

    @app.exception_handler(ValueError)
    async def _value(_: Request, exc: ValueError):
        return _error(422, str(exc) or "Los datos enviados no son válidos.", "invalid_data")
