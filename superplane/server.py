from __future__ import annotations

import base64
from typing import Any, TYPE_CHECKING

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .types import (
    ActionContext,
    CleanupContext,
    HttpResponse,
    SetupContext,
    WebhookContext,
    WebhookError,
    WebhookInfo,
    WebhookRequest,
    WebhookResult,
    WebhookSkip,
)

if TYPE_CHECKING:
    from .planelet import Planelet


def _serialize_params(parameters: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for param_id, param in parameters.items():
        entry: dict[str, Any] = {
            "id": param_id,
            "label": param.label,
            "type": param.type,
        }
        if param.description is not None:
            entry["description"] = param.description
        if param.required:
            entry["required"] = True
        if param.default is not None:
            entry["default"] = param.default
        if param.options is not None:
            entry["options"] = [
                {"label": o.label, "value": o.value} for o in param.options
            ]
        result.append(entry)
    return result


def _serialize_http_response(resp: HttpResponse | None) -> dict[str, Any] | None:
    if resp is None:
        return None
    out: dict[str, Any] = {"status": resp.status}
    if resp.headers:
        out["headers"] = resp.headers
    if resp.body is not None:
        out["body"] = resp.body
    return out


def build_app(planelet: Planelet) -> FastAPI:
    app = FastAPI(title=planelet.label)

    @app.get("/manifest")
    async def manifest() -> dict[str, Any]:
        actions = []
        for action_def in planelet._actions.values():
            entry: dict[str, Any] = {
                "id": action_def.id,
                "label": action_def.label,
                "parameters": _serialize_params(action_def.parameters),
            }
            if action_def.description:
                entry["description"] = action_def.description
            if action_def.icon:
                entry["icon"] = action_def.icon
            if action_def.icon_url:
                entry["iconUrl"] = action_def.icon_url
            actions.append(entry)

        triggers = []
        for trigger in planelet._triggers.values():
            entry = {
                "id": trigger.id,
                "label": trigger.label,
                "parameters": _serialize_params(trigger.parameters),
                "webhook": {"setup": "plugin"},
            }
            if trigger.description:
                entry["description"] = trigger.description
            if trigger.icon:
                entry["icon"] = trigger.icon
            if trigger.icon_url:
                entry["iconUrl"] = trigger.icon_url
            triggers.append(entry)

        result: dict[str, Any] = {
            "id": planelet.id,
            "label": planelet.label,
            "actions": actions,
            "triggers": triggers,
        }
        if planelet.icon:
            result["icon"] = planelet.icon
        if planelet.icon_url:
            result["iconUrl"] = planelet.icon_url
        if planelet.description:
            result["description"] = planelet.description
        return result

    @app.post("/actions/{action_id}/execute")
    async def execute_action(action_id: str, request: Request) -> JSONResponse:
        action_def = planelet._actions.get(action_id)
        if not action_def:
            return JSONResponse(
                {"success": False, "error": f'Action "{action_id}" not found'},
                status_code=404,
            )

        body = await request.json()
        ctx = ActionContext(
            parameters=body.get("parameters", {}),
            input=body.get("input"),
        )

        try:
            data = await action_def.handler(ctx)
            return JSONResponse({"success": True, "data": data})
        except Exception as exc:
            return JSONResponse(
                {"success": False, "error": str(exc)},
                status_code=500,
            )

    @app.post("/triggers/{trigger_id}/setup")
    async def setup_trigger(trigger_id: str, request: Request) -> JSONResponse:
        trigger = planelet._triggers.get(trigger_id)
        if not trigger:
            return JSONResponse(
                {"success": False, "error": f'Trigger "{trigger_id}" not found'},
                status_code=404,
            )
        if not trigger._setup:
            return JSONResponse(
                {"success": False, "error": f'Trigger "{trigger_id}" has no setup handler'},
                status_code=501,
            )

        body = await request.json()
        webhook_data = body.get("webhook", {})
        ctx = SetupContext(
            parameters=body.get("parameters", {}),
            webhook=WebhookInfo(
                url=webhook_data.get("url", ""),
                secret=webhook_data.get("secret"),
            ),
        )

        try:
            metadata = await trigger._setup(ctx)
            result: dict[str, Any] = {"success": True}
            if metadata:
                result["metadata"] = metadata
            return JSONResponse(result)
        except Exception as exc:
            return JSONResponse(
                {"success": False, "error": str(exc)},
                status_code=500,
            )

    @app.post("/triggers/{trigger_id}/cleanup")
    async def cleanup_trigger(trigger_id: str, request: Request) -> JSONResponse:
        trigger = planelet._triggers.get(trigger_id)
        if not trigger:
            return JSONResponse(
                {"success": False, "error": f'Trigger "{trigger_id}" not found'},
                status_code=404,
            )
        if not trigger._cleanup:
            return JSONResponse(
                {"success": False, "error": f'Trigger "{trigger_id}" has no cleanup handler'},
                status_code=501,
            )

        body = await request.json()
        ctx = CleanupContext(
            parameters=body.get("parameters", {}),
            metadata=body.get("metadata"),
        )

        try:
            await trigger._cleanup(ctx)
            return JSONResponse({"success": True})
        except Exception as exc:
            return JSONResponse(
                {"success": False, "error": str(exc)},
                status_code=500,
            )

    @app.post("/triggers/{trigger_id}/webhook")
    async def handle_webhook(trigger_id: str, request: Request) -> JSONResponse:
        trigger = planelet._triggers.get(trigger_id)
        if not trigger:
            return JSONResponse(
                {"success": False, "error": f'Trigger "{trigger_id}" not found'},
                status_code=404,
            )
        if not trigger._webhook:
            return JSONResponse(
                {"success": False, "error": f'Trigger "{trigger_id}" has no webhook handler'},
                status_code=501,
            )

        body = await request.json()
        req_data = body.get("request", {})
        raw_body_b64 = req_data.get("rawBodyBase64", "")
        raw_body = base64.b64decode(raw_body_b64) if raw_body_b64 else b""

        ctx = WebhookContext(
            parameters=body.get("parameters", {}),
            metadata=body.get("metadata"),
            request=WebhookRequest(
                method=req_data.get("method", "POST"),
                headers=req_data.get("headers", {}),
                query=req_data.get("query"),
                raw_body=raw_body,
            ),
        )

        try:
            result = await trigger._webhook(ctx)
        except Exception as exc:
            return JSONResponse(
                {"success": False, "error": str(exc)},
                status_code=500,
            )

        if isinstance(result, WebhookResult):
            resp: dict[str, Any] = {
                "success": True,
                "emit": True,
                "eventType": result.event_type,
                "payload": result.payload,
            }
            http_resp = _serialize_http_response(result.response)
            if http_resp:
                resp["response"] = http_resp
            return JSONResponse(resp)

        if isinstance(result, WebhookSkip):
            resp = {"success": True, "emit": False}
            if result.reason:
                resp["reason"] = result.reason
            http_resp = _serialize_http_response(result.response)
            if http_resp:
                resp["response"] = http_resp
            return JSONResponse(resp)

        if isinstance(result, WebhookError):
            err_resp: dict[str, Any] = {"success": False, "error": result.error}
            if result.status is not None:
                err_resp["status"] = result.status
            return JSONResponse(err_resp, status_code=result.status or 500)

        return JSONResponse(
            {"success": False, "error": "Webhook handler returned invalid type"},
            status_code=500,
        )

    return app
