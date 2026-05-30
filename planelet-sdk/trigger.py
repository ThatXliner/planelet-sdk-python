from __future__ import annotations

from typing import Any, Callable, Awaitable

from .types import (
    CleanupContext,
    Param,
    SetupContext,
    WebhookContext,
    WebhookError,
    WebhookResult,
    WebhookSkip,
)

SetupHandler = Callable[[SetupContext], Awaitable[dict[str, Any] | None]]
CleanupHandler = Callable[[CleanupContext], Awaitable[None]]
WebhookHandler = Callable[
    [WebhookContext], Awaitable[WebhookResult | WebhookSkip | WebhookError]
]


class TriggerBuilder:
    def __init__(
        self,
        id: str,
        *,
        label: str,
        description: str | None = None,
        icon: str | None = None,
        icon_url: str | None = None,
        parameters: dict[str, Param] | None = None,
    ) -> None:
        self.id = id
        self.label = label
        self.description = description
        self.icon = icon
        self.icon_url = icon_url
        self.parameters = parameters or {}

        self._setup: SetupHandler | None = None
        self._cleanup: CleanupHandler | None = None
        self._webhook: WebhookHandler | None = None

    def on_setup(self, fn: SetupHandler) -> SetupHandler:
        self._setup = fn
        return fn

    def on_cleanup(self, fn: CleanupHandler) -> CleanupHandler:
        self._cleanup = fn
        return fn

    def on_webhook(self, fn: WebhookHandler) -> WebhookHandler:
        self._webhook = fn
        return fn
