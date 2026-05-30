from __future__ import annotations

from typing import Any, Callable, Awaitable

from .trigger import TriggerBuilder
from .types import ActionContext, Param


ActionHandler = Callable[[ActionContext], Awaitable[dict[str, Any]]]


class _ActionDef:
    def __init__(
        self,
        id: str,
        *,
        label: str,
        description: str | None,
        icon: str | None,
        icon_url: str | None,
        parameters: dict[str, Param],
        handler: ActionHandler,
    ) -> None:
        self.id = id
        self.label = label
        self.description = description
        self.icon = icon
        self.icon_url = icon_url
        self.parameters = parameters
        self.handler = handler


class Planelet:
    def __init__(
        self,
        *,
        id: str,
        label: str,
        icon: str | None = None,
        icon_url: str | None = None,
        description: str | None = None,
    ) -> None:
        self.id = id
        self.label = label
        self.icon = icon
        self.icon_url = icon_url
        self.description = description

        self._actions: dict[str, _ActionDef] = {}
        self._triggers: dict[str, TriggerBuilder] = {}

    def action(
        self,
        id: str,
        *,
        label: str,
        description: str | None = None,
        icon: str | None = None,
        icon_url: str | None = None,
        parameters: dict[str, Param] | None = None,
    ) -> Callable[[ActionHandler], ActionHandler]:
        params = parameters or {}

        def decorator(fn: ActionHandler) -> ActionHandler:
            self._actions[id] = _ActionDef(
                id=id,
                label=label,
                description=description,
                icon=icon,
                icon_url=icon_url,
                parameters=params,
                handler=fn,
            )
            return fn

        return decorator

    def trigger(
        self,
        id: str,
        *,
        label: str,
        description: str | None = None,
        icon: str | None = None,
        icon_url: str | None = None,
        parameters: dict[str, Param] | None = None,
    ) -> TriggerBuilder:
        builder = TriggerBuilder(
            id,
            label=label,
            description=description,
            icon=icon,
            icon_url=icon_url,
            parameters=parameters,
        )
        self._triggers[id] = builder
        return builder

    def listen(self, port: int = 3000) -> None:
        from .server import build_app

        import uvicorn

        app = build_app(self)
        uvicorn.run(app, host="0.0.0.0", port=port)
