from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Param:
    label: str
    type: str  # "string" | "text" | "number" | "bool" | "select" | "object"
    description: str | None = None
    required: bool = False
    default: Any = None
    options: list[ParamOption] | None = None


@dataclass
class ParamOption:
    label: str
    value: str


# --- Contexts passed to handlers ---


@dataclass
class ActionContext:
    parameters: dict[str, Any]
    input: Any | None = None


@dataclass
class WebhookInfo:
    url: str
    secret: str | None = None


@dataclass
class SetupContext:
    parameters: dict[str, Any]
    webhook: WebhookInfo = field(default_factory=lambda: WebhookInfo(url=""))


@dataclass
class CleanupContext:
    parameters: dict[str, Any]
    metadata: dict[str, Any] | None = None


@dataclass
class WebhookRequest:
    method: str
    headers: dict[str, list[str]]
    query: dict[str, list[str]] | None = None
    raw_body: bytes = b""


@dataclass
class WebhookContext:
    parameters: dict[str, Any]
    metadata: dict[str, Any] | None = None
    request: WebhookRequest = field(
        default_factory=lambda: WebhookRequest(method="POST", headers={})
    )


# --- Result types returned by handlers ---


@dataclass
class HttpResponse:
    status: int = 200
    headers: dict[str, str] | None = None
    body: str | None = None


@dataclass
class WebhookResult:
    event_type: str
    payload: Any = None
    response: HttpResponse | None = None


@dataclass
class WebhookSkip:
    reason: str | None = None
    response: HttpResponse | None = None
