"""Asistente con IA: guía que explica la pantalla, interpreta resultados y orienta el muestreo.

- GET  /api/assistant/status (sin cuerpo)        -> AssistantStatus
- POST /api/assistant/chat   (AssistantRequest)  -> flujo `text/event-stream`

La API sigue sin estado: la web envía en cada petición la conversación completa
y el contexto de lo que el usuario tiene en pantalla. El asistente no recalcula
por su cuenta: los números salen del contexto (resultados ya devueltos por esta
API) o de herramientas que llaman a `app/spc/`.

Flujo de respuesta (Server-Sent Events). Cada evento es `event: <tipo>` y
`data: <JSON>`:

- `delta`  {"text": str}                      fragmento de texto de la respuesta
- `tool`   {"name": str, "label": str}        el asistente está calculando algo
- `done`   {"stop_reason": str}               fin normal de la respuesta
- `error`  {"detail": str, "code": str}       fin con error (mensaje en español)

Errores antes de abrir el flujo usan `ErrorResponse` como el resto de rutas:
401 sin sesión, 403 si los invitados no tienen acceso, 422 por validación y
503 si el asistente no está configurado.
"""

from typing import Any, Literal, Optional

from pydantic import Field

from .common import Model

AssistantScreen = Literal[
    "studies",
    "study",
    "data",
    "variables",
    "attributes",
    "assumptions",
    "capability",
    "design",
    "sampling",
    "report",
]


class AssistantStatus(Model):
    enabled: bool = Field(description="Hay credenciales del proveedor de IA configuradas")
    available: bool = Field(description="El usuario de esta sesión puede usarlo")
    reason: Optional[str] = Field(default=None, description="Si no está disponible, por qué (en español)")
    guests_allowed: bool


class AssistantMessage(Model):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=6000)


class AssistantStudy(Model):
    """Ficha del estudio abierto. Todos los campos son opcionales."""

    name: Optional[str] = Field(default=None, max_length=200)
    company: Optional[str] = Field(default=None, max_length=200)
    process: Optional[str] = Field(default=None, max_length=300)
    product: Optional[str] = Field(default=None, max_length=300)
    characteristic: Optional[str] = Field(default=None, max_length=300)
    unit: Optional[str] = Field(default=None, max_length=40)
    data_type: Optional[Literal["variable", "attribute"]] = None
    lsl: Optional[float] = None
    usl: Optional[float] = None
    target: Optional[float] = None
    synthetic: Optional[bool] = Field(default=None, description="El estudio está marcado como datos sintéticos")
    notes: Optional[str] = Field(default=None, max_length=2000)


class AssistantContext(Model):
    """Lo que el usuario está viendo. La web lo arma en cada pantalla."""

    screen: AssistantScreen
    study: Optional[AssistantStudy] = None
    view: Optional[dict[str, Any]] = Field(
        default=None,
        description=(
            "Estado de la pantalla en JSON libre: parámetros elegidos y, si ya se calculó, "
            "la respuesta de la API de ese módulo (sin series largas). La ruta limita su "
            "tamaño serializado y responde 422 si lo supera."
        ),
    )
    datasets: Optional[list[dict[str, Any]]] = Field(
        default=None,
        max_length=20,
        description="Resumen de los conjuntos de datos del estudio: nombre, fase, tamaños; nunca las filas",
    )
    frozen_limits: Optional[list[dict[str, Any]]] = Field(
        default=None, max_length=10, description="Límites de Fase I congelados vigentes"
    )


class AssistantRequest(Model):
    messages: list[AssistantMessage] = Field(min_length=1, max_length=30)
    context: AssistantContext
