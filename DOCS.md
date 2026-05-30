# SuperPlane Planelet SDK for Python

Build custom SuperPlane integrations without modifying the SuperPlane codebase. Write a Planelet server with the Python SDK, point SuperPlane at it, and your actions and triggers appear natively in the canvas UI.

## Architecture

```
┌──────────────┐           ┌──────────────────┐         ┌────────────────┐
│  SuperPlane  │ ──GET───▶ │ Planelet Server  │         │   Your Code    │
│  (Planelets  │ /manifest │  (SDK-powered)   │◀────────│   (actions,    │
│  Integration)│           │                  │         │    triggers,   │
│              │ ──POST──▶ │ /actions/:id/    │         │    logic)      │
│              │           │    execute       │         │                │
│              │ ──POST──▶ │ /triggers/:id/   │         │                │
│              │           │    setup/webhook │         │                │
│              │ ◀──POST── │ POST events to   │         │                │
│              │           │ SuperPlane       │         │                │
└──────────────┘           └──────────────────┘         └────────────────┘
```

1. You build a Planelet server using the SDK
2. SuperPlane's Planelets integration connects to your server
3. On setup, it fetches your manifest to discover available actions and triggers
4. When a canvas node runs your action, SuperPlane proxies the execution to your server
5. When a trigger is published, SuperPlane calls your setup handler with a webhook URL
6. When a third-party webhook fires, SuperPlane forwards it to your webhook handler
7. Your server can also push events directly to SuperPlane

## Quick Start

### 1. Create a new project

```bash
mkdir my-planelet && cd my-planelet
python -m venv .venv && source .venv/bin/activate
pip install superplane-planelet-sdk
```

### 2. Write your Planelet

```python
# main.py
from superplane import create_planelet, Param, ActionContext

planelet = create_planelet(
    id="my-planelet",
    label="My Planelet",
    description="Does useful things",
)

@planelet.action(
    "hello",
    label="Say Hello",
    description="Generates a greeting",
    parameters={
        "name": Param(label="Name", type="string", required=True),
    },
)
async def hello(ctx: ActionContext):
    return {"message": f"Hello, {ctx.parameters['name']}!"}

planelet.listen(3001)
```

### 3. Run it

```bash
python main.py
# Uvicorn running on http://0.0.0.0:3001
```

### 4. Connect to SuperPlane

1. In SuperPlane, add a new **Planelets** integration
2. Set **Server URL** to your Planelet server's address (e.g. `https://my-planelet.example.com`)
3. Optionally set an **Auth Token**
4. Save — SuperPlane fetches your manifest and the integration goes ready

### 5. Use in a canvas

Add a **Run Planelet Action** node to your canvas. Select your action from the dropdown. Fill in the parameters. Done.

---

## SDK API Reference

### `create_planelet(**options)`

Creates a new Planelet instance.

```python
from superplane import create_planelet

planelet = create_planelet(
    id="my-planelet",          # required — stable identifier
    label="My Planelet",       # required — display name
    icon="puzzle",             # optional — Lucide icon slug
    icon_url="https://...",    # optional — custom icon URL (overrides icon)
    description="...",         # optional
)
```

### `@planelet.action(id, **options)`

Registers an action via decorator. The decorated function receives an `ActionContext` and must return a dict.

```python
@planelet.action(
    "do-thing",
    label="Do Thing",                     # required — display name
    description="Does a thing",           # optional
    icon="zap",                           # optional — action-level icon
    icon_url="https://...",               # optional — action-level custom icon
    parameters={                          # optional — config fields
        "my_field": Param(
            label="My Field",
            type="string",
            required=True,
            description="What it does",
        ),
    },
)
async def do_thing(ctx: ActionContext):
    # ctx.parameters = {"my_field": "value"}
    # ctx.input = data from upstream canvas node (or None)
    return {"result": "ok"}
```

Raising an exception from the handler produces a failure response automatically.

### `planelet.trigger(id, **options)`

Registers a trigger and returns a `TriggerBuilder`. Use sub-decorators to attach lifecycle hooks.

```python
my_trigger = planelet.trigger(
    "on-event",
    label="On Event",                     # required — display name
    description="Fires on events",        # optional
    icon="bell",                          # optional
    icon_url="https://...",               # optional
    parameters={                          # optional
        "channel": Param(label="Channel", type="string", required=True),
    },
)
```

#### `@trigger.on_setup`

Called when SuperPlane publishes the trigger. Use this to register a webhook with the third-party service.

```python
@my_trigger.on_setup
async def setup(ctx: SetupContext):
    # ctx.parameters = {"channel": "general"}
    # ctx.webhook.url = "https://superplane.dev/wh/abc123"
    # ctx.webhook.secret = "optional-shared-secret" or None

    await some_api.create_webhook(url=ctx.webhook.url)
    return {"provider_webhook_id": "wh_456"}  # stored as metadata
```

Return a dict to store metadata. SuperPlane passes this metadata back in future webhook and cleanup calls.

#### `@trigger.on_cleanup`

Called when the trigger is removed. Use this to unregister the third-party webhook.

```python
@my_trigger.on_cleanup
async def cleanup(ctx: CleanupContext):
    # ctx.parameters = {"channel": "general"}
    # ctx.metadata = {"provider_webhook_id": "wh_456"}

    if ctx.metadata and ctx.metadata.get("provider_webhook_id"):
        await some_api.delete_webhook(ctx.metadata["provider_webhook_id"])
```

#### `@trigger.on_webhook`

Called when SuperPlane receives a third-party webhook. Verify, filter, and normalize the event here.

Return `WebhookResult` to emit an event into the workflow, or `WebhookSkip` to silently ignore it.

```python
import json
from superplane import WebhookResult, WebhookSkip

@my_trigger.on_webhook
async def handle(ctx: WebhookContext):
    # ctx.parameters = {"channel": "general"}
    # ctx.metadata = {"provider_webhook_id": "wh_456"}
    # ctx.request.method = "POST"
    # ctx.request.headers = {"content-type": ["application/json"], ...}
    # ctx.request.query = {"token": ["abc"]} or None
    # ctx.request.raw_body = b'{"event": "message", ...}'  (decoded from base64)

    body = json.loads(ctx.request.raw_body)

    # Filter: ignore non-message events
    if body.get("type") != "message":
        return WebhookSkip(reason="not a message event")

    # Emit: normalize and pass into workflow
    return WebhookResult(
        event_type="chat.message",
        payload={
            "channel": body["channel"],
            "text": body["text"],
            "user": body["user"],
        },
    )
```

You can optionally include an HTTP response to send back to the third party:

```python
from superplane import HttpResponse

return WebhookResult(
    event_type="chat.message",
    payload={...},
    response=HttpResponse(status=200, body="ok"),
)
```

### `planelet.listen(port)`

Starts the HTTP server using uvicorn.

```python
planelet.listen(3001)
```

---

## Types Reference

### `Param`

Defines a user-configurable parameter field.

```python
from superplane import Param, ParamOption

Param(
    label="Display Name",        # required
    type="string",               # required — see Parameter Types table
    description="Help text",     # optional
    required=True,               # optional — default False
    default="value",             # optional
    options=[                    # required for "select" type
        ParamOption(label="Option A", value="a"),
        ParamOption(label="Option B", value="b"),
    ],
)
```

### Parameter Types

| Type     | Description            | Extra options                   |
| -------- | ---------------------- | ------------------------------- |
| `string` | Single-line text input | —                               |
| `text`   | Multi-line text input  | —                               |
| `number` | Numeric input          | —                               |
| `bool`   | Boolean checkbox       | —                               |
| `select` | Dropdown selection     | `options: [ParamOption(…), …]`  |
| `object` | JSON object editor     | —                               |

### Context Types

| Type             | Fields                                                                                              |
| ---------------- | --------------------------------------------------------------------------------------------------- |
| `ActionContext`  | `parameters: dict[str, Any]`, `input: Any \| None`                                                  |
| `SetupContext`   | `parameters: dict[str, Any]`, `webhook: WebhookInfo`                                                |
| `CleanupContext` | `parameters: dict[str, Any]`, `metadata: dict[str, Any] \| None`                                    |
| `WebhookContext` | `parameters: dict[str, Any]`, `metadata: dict[str, Any] \| None`, `request: WebhookRequest`         |

### Supporting Types

| Type             | Fields                                                                                          |
| ---------------- | ----------------------------------------------------------------------------------------------- |
| `WebhookInfo`    | `url: str`, `secret: str \| None`                                                                |
| `WebhookRequest` | `method: str`, `headers: dict[str, list[str]]`, `query: dict[str, list[str]] \| None`, `raw_body: bytes` |

### Result Types

| Type            | Fields                                                                |
| --------------- | --------------------------------------------------------------------- |
| `WebhookResult` | `event_type: str`, `payload: Any`, `response: HttpResponse \| None`   |
| `WebhookSkip`   | `reason: str \| None`, `response: HttpResponse \| None`               |
| `HttpResponse`  | `status: int`, `headers: dict[str, str] \| None`, `body: str \| None` |

---

## Protocol Reference

The SDK handles all of this for you, but here's the raw protocol if you need to understand what's happening under the hood.

### `GET /manifest`

Returns the Planelet's metadata, actions, and triggers.

**Response:**

```json
{
  "id": "my-planelet",
  "label": "My Planelet",
  "icon": "puzzle",
  "description": "Does useful things",
  "actions": [
    {
      "id": "hello",
      "label": "Say Hello",
      "description": "Generates a greeting",
      "parameters": [
        {
          "id": "name",
          "label": "Name",
          "type": "string",
          "required": true
        }
      ]
    }
  ],
  "triggers": [
    {
      "id": "on-event",
      "label": "On Event",
      "parameters": [
        {
          "id": "channel",
          "label": "Channel",
          "type": "string",
          "required": true
        }
      ],
      "webhook": {
        "setup": "plugin"
      }
    }
  ]
}
```

### `POST /actions/{actionId}/execute`

Executes an action.

**Request:**

```json
{
  "parameters": { "name": "World" },
  "input": { "upstream": "data" }
}
```

**Success (200):**

```json
{
  "success": true,
  "data": { "message": "Hello, World!" }
}
```

**Error (4xx/5xx):**

```json
{
  "success": false,
  "error": "Something went wrong"
}
```

### `POST /triggers/{triggerId}/setup`

Called when a trigger node is published. The Planelet should register a webhook with the third-party service.

**Request:**

```json
{
  "parameters": { "channel": "general" },
  "webhook": {
    "url": "https://superplane.dev/wh/abc123",
    "secret": "optional-shared-secret"
  }
}
```

**Success (200):**

```json
{
  "success": true,
  "metadata": { "provider_webhook_id": "wh_456" }
}
```

### `POST /triggers/{triggerId}/cleanup`

Called when the trigger is removed. The Planelet should unregister the third-party webhook.

**Request:**

```json
{
  "parameters": { "channel": "general" },
  "metadata": { "provider_webhook_id": "wh_456" }
}
```

**Success (200):**

```json
{ "success": true }
```

### `POST /triggers/{triggerId}/webhook`

Called when SuperPlane receives a third-party webhook. The Planelet verifies, filters, and normalizes the event.

**Request:**

```json
{
  "parameters": { "channel": "general" },
  "metadata": { "provider_webhook_id": "wh_456" },
  "request": {
    "method": "POST",
    "headers": { "content-type": ["application/json"] },
    "query": { "token": ["abc"] },
    "rawBodyBase64": "eyJldmVudCI6ICJtZXNzYWdlIn0="
  }
}
```

**Emit event (200):**

```json
{
  "success": true,
  "emit": true,
  "eventType": "chat.message",
  "payload": { "text": "hello" },
  "response": { "status": 200, "body": "ok" }
}
```

**Skip event (200):**

```json
{
  "success": true,
  "emit": false,
  "reason": "ping event, ignored"
}
```

### Direct Events

Planelets can also push events directly to SuperPlane without a third-party webhook:

```
POST /api/v1/integrations/{integrationId}/events
Content-Type: application/json

{
  "eventType": "my.event.type",
  "payload": { ... }
}
```

Use the **On Planelet Event** trigger in your canvas to listen for these events.

---

## Authentication

If your Planelet server requires authentication, set the **Auth Token** in the SuperPlane Planelets integration config. The token is sent as a `Bearer` token in the `Authorization` header on every request from SuperPlane to your server.

To validate it server-side, add FastAPI middleware or a dependency:

```python
from fastapi import Depends, HTTPException, Header

async def verify_token(authorization: str = Header()):
    if authorization != "Bearer my-secret-token":
        raise HTTPException(status_code=401, detail="Unauthorized")

# Access the underlying FastAPI app to add dependencies:
from superplane.server import build_app
app = build_app(planelet)
# Add auth dependency to all routes as needed
```

---

## Deploying

Your Planelet server is a standard HTTP server. Deploy it anywhere SuperPlane can reach:

- **Local development**: `localhost` or tunnel (ngrok, cloudflared)
- **Cloud**: any container platform (Railway, Fly.io, Cloud Run, ECS)
- **Self-hosted**: any server with a public or VPN-accessible URL

The server must be reachable from SuperPlane at the configured URL. HTTPS is recommended for production.

---

## Complete Example

A Planelet with both actions and triggers:

```python
import json
from superplane import (
    create_planelet,
    Param,
    ParamOption,
    ActionContext,
    SetupContext,
    CleanupContext,
    WebhookContext,
    WebhookResult,
    WebhookSkip,
)

planelet = create_planelet(
    id="slack-lite",
    label="Slack Lite",
    icon_url="https://example.com/slack.svg",
    description="Lightweight Slack integration",
)

# --- Actions ---

@planelet.action(
    "send-message",
    label="Send Message",
    parameters={
        "channel": Param(label="Channel", type="string", required=True),
        "text": Param(label="Message", type="text", required=True),
    },
)
async def send_message(ctx: ActionContext):
    # In reality, call the Slack API here
    return {"ok": True, "channel": ctx.parameters["channel"]}


# --- Triggers ---

messages_trigger = planelet.trigger(
    "new-message",
    label="New Message",
    description="Fires when a message is posted",
    parameters={
        "channel": Param(label="Channel", type="string", required=True),
    },
)

@messages_trigger.on_setup
async def setup(ctx: SetupContext):
    # Register webhook with Slack (simplified)
    # webhook_id = await slack.create_webhook(ctx.webhook.url, ctx.parameters["channel"])
    webhook_id = "wh_mock_123"
    return {"webhook_id": webhook_id}

@messages_trigger.on_cleanup
async def cleanup(ctx: CleanupContext):
    if ctx.metadata and ctx.metadata.get("webhook_id"):
        # await slack.delete_webhook(ctx.metadata["webhook_id"])
        pass

@messages_trigger.on_webhook
async def handle(ctx: WebhookContext):
    body = json.loads(ctx.request.raw_body)

    # Slack sends URL verification challenges
    if body.get("type") == "url_verification":
        return WebhookSkip(reason="url verification challenge")

    if body.get("type") != "event_callback":
        return WebhookSkip(reason=f"ignored event type: {body.get('type')}")

    event = body.get("event", {})
    return WebhookResult(
        event_type="slack.message",
        payload={
            "channel": event.get("channel"),
            "user": event.get("user"),
            "text": event.get("text"),
            "ts": event.get("ts"),
        },
    )

planelet.listen(3001)
```
