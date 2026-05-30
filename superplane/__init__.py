from .planelet import Planelet
from .types import (
    ActionContext,
    CleanupContext,
    HttpResponse,
    Param,
    ParamOption,
    SetupContext,
    WebhookContext,
    WebhookInfo,
    WebhookRequest,
    WebhookResult,
    WebhookSkip,
)
from .trigger import TriggerBuilder


def create_planelet(
    *,
    id: str,
    label: str,
    icon: str | None = None,
    icon_url: str | None = None,
    description: str | None = None,
) -> Planelet:
    return Planelet(
        id=id,
        label=label,
        icon=icon,
        icon_url=icon_url,
        description=description,
    )


__all__ = [
    "create_planelet",
    "ActionContext",
    "CleanupContext",
    "HttpResponse",
    "Param",
    "ParamOption",
    "Planelet",
    "SetupContext",
    "TriggerBuilder",
    "WebhookContext",
    "WebhookInfo",
    "WebhookRequest",
    "WebhookResult",
    "WebhookSkip",
]
