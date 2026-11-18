"""Asistente con IA: estado y chat en streaming (Server-Sent Events).

Decisiones:
- Cliente asíncrono (`AsyncAnthropic`) y bucle de herramientas manual con
  `client.beta.messages.stream(...)`. Es el modelo natural de FastAPI/ASGI en Vercel: el
  generador asíncrono entrega cada fragmento al navegador sin hilos ni bloqueo del event
  loop. Las herramientas son cálculo numérico síncrono: se ejecutan con
  `asyncio.to_thread` y un tiempo máximo. Se prefiere el bucle manual al tool runner
  porque deja comprobar `stop_reason` antes de ejecutar nada y validar cada entrada.
- Caché de prompt: herramientas y `system` (estables) primero, con `cache_control` en el
  último bloque del `system`. El contexto de la pantalla viaja en el último mensaje del
  usuario, después del punto de corte.
- Sin estado: no hay cuotas por usuario. Los límites son por petición (tamaño del
  contexto, tokens de salida, iteraciones del bucle, tiempo total).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, AsyncIterator, Optional

import anthropic
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse

from app.assistant_prompt import SYSTEM_PROMPT, render_context
from app.assistant_tools import TOOLS, ToolError, tool_definitions
from app.auth import require_auth
from app.schemas.assistant import AssistantRequest, AssistantStatus

logger = logging.getLogger("sigmalena.assistant")

router = APIRouter(tags=["asistente"])

# --- Límites y valores por defecto (algunos se sobreescriben con variables de entorno) ---
DEFAULT_MODEL = "claude-opus-5-5"  # ASSISTANT_MODEL
DEFAULT_EFFORT = "medium"  # ASSISTANT_EFFORT
EFFORTS = ("low", "medium", "high", "xhigh", "max")
DEFAULT_MAX_TOKENS = 4000  # ASSISTANT_MAX_TOKENS
MIN_MAX_TOKENS, MAX_MAX_TOKENS = 256, 16000
MAX_CONTEXT_BYTES = 60_000  # tamaño serializado de `context`; más -> 422
MAX_TOOL_ITERATIONS = 6  # llamadas al modelo por petición (incluye la respuesta final)
MAX_TOOLS_PER_TURN = 4
TOOL_TIMEOUT_SECONDS = 20.0
DEFAULT_TIME_BUDGET_SECONDS = 240.0  # ASSISTANT_TIME_BUDGET; por debajo del límite de la función
FALLBACK_BETA = "server-side-fallback-2026-07-01"
FALLBACK_MODEL_PREFIXES = ("claude-opus-5", "claude-fable-5", "claude-sonnet-5-5")

SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


# --- Configuración ------------------------------------------------------------------
def api_key_configured() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


def guests_allowed() -> bool:
    return os.environ.get("ASSISTANT_ALLOW_GUESTS", "").strip() == "1"


def model_name() -> str:
    return os.environ.get("ASSISTANT_MODEL", "").strip() or DEFAULT_MODEL


def effort() -> str:
    value = os.environ.get("ASSISTANT_EFFORT", "").strip().lower()
    return value if value in EFFORTS else DEFAULT_EFFORT


def max_tokens() -> int:
    try:
        value = int(os.environ.get("ASSISTANT_MAX_TOKENS", ""))
    except ValueError:
        return DEFAULT_MAX_TOKENS
    return max(MIN_MAX_TOKENS, min(MAX_MAX_TOKENS, value))


def time_budget() -> float:
    try:
        return max(10.0, float(os.environ.get("ASSISTANT_TIME_BUDGET", "")))
    except ValueError:
        return DEFAULT_TIME_BUDGET_SECONDS


def make_client() -> anthropic.AsyncAnthropic:
    """Fábrica del cliente; las pruebas la sustituyen por un doble."""
    return anthropic.AsyncAnthropic(timeout=anthropic.Timeout(120.0, connect=10.0), max_retries=2)


def is_guest(claims: Optional[dict[str, Any]]) -> bool:
    """Sesión anónima de Supabase (claim `is_anonymous`). Con AUTH_DISABLED no hay claims: usuario normal."""
    return bool(claims) and claims.get("is_anonymous") is True


def _error_response(status: int, detail: str, code: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": detail, "code": code})


def _access_error(claims: Optional[dict[str, Any]]) -> Optional[JSONResponse]:
    if not api_key_configured():
        return _error_response(503, "El asistente no está configurado en este servidor.", "assistant_unavailable")
    if is_guest(claims) and not guests_allowed():
        return _error_response(403, "Crea una cuenta para usar el asistente.", "forbidden")
    return None


# --- Rutas --------------------------------------------------------------------------
@router.get("/api/assistant/status", response_model=AssistantStatus)
def assistant_status(claims: Optional[dict] = Depends(require_auth)):
    enabled = api_key_configured()
    allowed = guests_allowed()
    reason: Optional[str] = None
    if not enabled:
        reason = "El asistente no está configurado en este servidor."
    elif is_guest(claims) and not allowed:
        reason = "Crea una cuenta para usar el asistente."
    return AssistantStatus(enabled=enabled, available=reason is None, reason=reason, guests_allowed=allowed)


@router.post(
    "/api/assistant/chat",
    response_class=StreamingResponse,
    responses={
        200: {"description": "Flujo `text/event-stream` con eventos delta, tool, done y error",
              "content": {"text/event-stream": {}}},
        403: {"description": "Los invitados no tienen acceso"},
        503: {"description": "El asistente no está configurado"},
    },
)
async def assistant_chat(body: AssistantRequest, claims: Optional[dict] = Depends(require_auth)):
    blocked = _access_error(claims)
    if blocked is not None:
        return blocked
    if body.messages[-1].role != "user":
        raise ValueError("El último mensaje de la conversación debe ser del usuario.")
    context = body.context.model_dump(mode="json", exclude_none=True)
    size = len(json.dumps(context, ensure_ascii=False).encode("utf-8"))
    if size > MAX_CONTEXT_BYTES:
        raise ValueError(
            f"El contexto de la pantalla es demasiado grande ({size // 1000} KB; el máximo es "
            f"{MAX_CONTEXT_BYTES // 1000} KB). Envía un resumen del resultado, sin series largas."
        )
    messages = build_messages(body, render_context(context))
    stream = run_chat(make_client(), messages)
    return StreamingResponse(_sse(stream), media_type="text/event-stream", headers=SSE_HEADERS)


# --- Construcción de la petición ----------------------------------------------------
def build_messages(body: AssistantRequest, context_block: str) -> list[dict[str, Any]]:
    """Historial tal cual; el contexto (volátil) va en el último mensaje del usuario."""
    turns = [{"role": m.role, "content": m.content} for m in body.messages]
    while turns and turns[0]["role"] == "assistant":  # la API exige empezar por el usuario (p. ej. un saludo)
        turns.pop(0)
    last = turns[-1]
    last["content"] = [
        {"type": "text", "text": context_block},
        {"type": "text", "text": last["content"]},
    ]
    return turns


def request_params(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Parámetros de cada llamada al modelo. Sin temperature, top_p, top_k, budget_tokens,
    tool_choice forzado ni prefill (rechazados por Claude Opus 5.5)."""
    model = model_name()
    params: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens(),
        "system": [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        "tools": tool_definitions(),
        "messages": messages,
        "output_config": {"effort": effort()},
    }
    if model.startswith(FALLBACK_MODEL_PREFIXES):
        params["betas"] = [FALLBACK_BETA]
        params["fallbacks"] = "default"
    return params


def echo_content(content: list[Any]) -> list[Any]:
    """Tras un fallback a mitad de salida, la API pide no reenviar thinking ni tool_use
    anteriores al último bloque `fallback`."""
    boundary = max((i for i, b in enumerate(content) if getattr(b, "type", "") == "fallback"), default=-1)
    return [
        b for i, b in enumerate(content)
        if not (i < boundary and getattr(b, "type", "") in ("thinking", "redacted_thinking", "tool_use"))
    ]


# --- Bucle del asistente --------------------------------------------------------------
Event = tuple[str, dict[str, Any]]


def _sse(events: AsyncIterator[Event]) -> AsyncIterator[str]:
    async def generate():
        async for name, data in events:
            yield f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    return generate()


def _error(code: str, detail: str) -> Event:
    return "error", {"detail": detail, "code": code}


def sdk_error_event(exc: BaseException) -> Event:
    """Cadena tipada, de lo más específico a lo más general. Nunca incluye el mensaje original."""
    if isinstance(exc, (anthropic.AuthenticationError, anthropic.PermissionDeniedError)):
        return _error("assistant_config", "El asistente no está bien configurado en el servidor. Avisa al administrador.")
    if isinstance(exc, anthropic.RateLimitError):
        return _error("rate_limited", "El asistente está recibiendo muchas consultas. Espera un momento e inténtalo de nuevo.")
    if isinstance(exc, anthropic.RequestTooLargeError):
        return _error("too_large", "La conversación es demasiado larga. Empieza una nueva o acórtala.")
    if isinstance(exc, anthropic.BadRequestError):
        if "credit balance" in str(getattr(exc, "message", "")).lower():  # facturación: problema del servidor, no de la consulta
            return _error("assistant_config", "El asistente no está disponible por un problema de la cuenta del servicio. Avisa al administrador.")
        return _error("bad_request", "El asistente no pudo procesar esta consulta. Reformúlala o empieza una conversación nueva.")
    if isinstance(exc, (anthropic.OverloadedError, anthropic.InternalServerError, anthropic.ServiceUnavailableError)):
        return _error("overloaded", "El servicio de IA está saturado o con fallas. Inténtalo de nuevo en unos minutos.")
    if isinstance(exc, anthropic.APITimeoutError):
        return _error("timeout", "El asistente tardó demasiado en responder. Inténtalo de nuevo.")
    if isinstance(exc, anthropic.APIConnectionError):
        return _error("connection", "No se pudo conectar con el servicio de IA. Revisa la conexión e inténtalo de nuevo.")
    if isinstance(exc, anthropic.APIStatusError):
        return _error("api_error", "El servicio de IA respondió con un error. Inténtalo de nuevo.")
    return _error("assistant_error", "El asistente tuvo un problema inesperado. Inténtalo de nuevo.")


async def run_tool(block: Any) -> tuple[dict[str, Any], str]:
    """Valida y ejecuta una herramienta. Devuelve (tool_result, etiqueta); nunca lanza."""
    result: dict[str, Any] = {"type": "tool_result", "tool_use_id": block.id}
    tool = TOOLS.get(block.name)
    args = block.input
    if tool is None or not isinstance(args, dict):
        result.update(is_error=True, content="Herramienta o entrada no válida.")
        return result, ""
    try:
        output = await asyncio.wait_for(asyncio.to_thread(tool.run, args), TOOL_TIMEOUT_SECONDS)
        result["content"] = json.dumps(output, ensure_ascii=False)
    except asyncio.TimeoutError:
        result.update(is_error=True, content="El cálculo tardó demasiado; prueba con parámetros más simples.")
    except ValueError as exc:  # ToolError y los ValueError de spc/ (mensajes en español)
        result.update(is_error=True, content=str(exc) or "Parámetros no válidos.")
        if not isinstance(exc, ToolError):
            logger.info("tool %s rechazó la entrada", block.name)
    except Exception:
        logger.exception("fallo inesperado en la herramienta %s", block.name)
        result.update(is_error=True, content="Fallo interno al calcular.")
    return result, tool.label


async def run_chat(client: Any, messages: list[dict[str, Any]]) -> AsyncIterator[Event]:
    """Conversa con el modelo y ejecuta herramientas hasta la respuesta final.

    Eventos: delta, tool, done, error. Siempre termina con `done` o `error`."""
    started = time.monotonic()
    budget = time_budget()
    try:
        for iteration in range(MAX_TOOL_ITERATIONS):
            if time.monotonic() - started > budget:
                yield _error("timeout", "La consulta tardó demasiado. Inténtalo de nuevo con una pregunta más acotada.")
                return
            async with client.beta.messages.stream(**request_params(messages)) as stream:
                async for event in stream:
                    if event.type == "text" and event.text:
                        yield "delta", {"text": event.text}
                final = await stream.get_final_message()

            reason = final.stop_reason
            if reason == "refusal":
                yield _error("refusal", "No puedo ayudar con esa consulta. Reformúlala sobre estadística de calidad o el uso del programa.")
                return
            if reason == "max_tokens":  # nunca se ejecutan herramientas de un turno truncado
                yield "done", {"stop_reason": "max_tokens"}
                return
            tool_uses = [b for b in final.content if getattr(b, "type", "") == "tool_use"]
            if reason != "tool_use" or not tool_uses:
                yield "done", {"stop_reason": reason or "end_turn"}
                return
            if iteration == MAX_TOOL_ITERATIONS - 1:
                yield _error("tool_limit", "La consulta requería demasiados cálculos. Pregunta por partes.")
                return

            results = []
            for index, block in enumerate(tool_uses):
                if index >= MAX_TOOLS_PER_TURN:
                    results.append({"type": "tool_result", "tool_use_id": block.id, "is_error": True,
                                    "content": "Demasiados cálculos en un solo paso; pide menos a la vez."})
                    continue
                tool = TOOLS.get(block.name)
                if tool is not None and isinstance(block.input, dict):
                    yield "tool", {"name": tool.name, "label": tool.label}
                result, _ = await run_tool(block)
                results.append(result)
            messages = messages + [
                {"role": "assistant", "content": echo_content(final.content)},
                {"role": "user", "content": results},
            ]
    except anthropic.AnthropicError as exc:
        logger.warning("error del SDK: %s (request_id=%s)", type(exc).__name__, getattr(exc, "request_id", None))
        yield sdk_error_event(exc)
    except ValueError:  # JSON de herramienta ilegible dentro del flujo (eager_input_streaming)
        logger.warning("entrada de herramienta ilegible en el flujo")
        yield _error("invalid_tool_input", "El asistente no pudo preparar un cálculo. Inténtalo de nuevo.")
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("fallo inesperado en el asistente")
        yield sdk_error_event(RuntimeError())
