import hashlib
import hmac
import json
import random

from planelet_sdk import (
    ActionContext,
    CleanupContext,
    HttpResponse,
    Param,
    ParamOption,
    SetupContext,
    WebhookContext,
    WebhookResult,
    WebhookSkip,
    create_planelet,
)

planelet = create_planelet(
    id="quotes",
    label="Random Quotes",
    icon="quote",
    description="Get random quotes via actions or receive them via webhook",
)

QUOTES = [
    {"text": "The only way to do great work is to love what you do.", "author": "Steve Jobs"},
    {"text": "Innovation distinguishes between a leader and a follower.", "author": "Steve Jobs"},
    {"text": "Stay hungry, stay foolish.", "author": "Steve Jobs"},
    {"text": "Move fast and break things.", "author": "Mark Zuckerberg"},
    {"text": "The best way to predict the future is to invent it.", "author": "Alan Kay"},
    {"text": "Talk is cheap. Show me the code.", "author": "Linus Torvalds"},
]


# ── Action (planelet event) ──────────────────────────────────────────
# Actions are user-invoked: a user clicks a button, SuperPlane calls
# /actions/{id}/execute, and the handler returns data synchronously.


@planelet.action(
    "get-quote",
    label="Get Random Quote",
    description="Returns a random inspirational quote",
    parameters={
        "category": Param(
            label="Category",
            type="select",
            description="Filter quotes by category",
            options=[
                ParamOption(label="All", value="all"),
                ParamOption(label="Innovation", value="innovation"),
                ParamOption(label="Motivation", value="motivation"),
            ],
        ),
    },
)
async def get_quote(ctx: ActionContext) -> dict:
    quote = random.choice(QUOTES)
    return {"quote": quote["text"], "author": quote["author"]}


@planelet.action(
    "greet",
    label="Generate Greeting",
    description="Generate a personalized greeting message",
    parameters={
        "name": Param(
            label="Name",
            type="string",
            description="Name of the person to greet",
            required=True,
        ),
        "style": Param(
            label="Style",
            type="select",
            description="Greeting style",
            required=True,
            options=[
                ParamOption(label="Formal", value="formal"),
                ParamOption(label="Casual", value="casual"),
                ParamOption(label="Enthusiastic", value="enthusiastic"),
            ],
        ),
    },
)
async def greet(ctx: ActionContext) -> dict:
    name = ctx.parameters["name"]
    style = ctx.parameters.get("style", "casual")

    greetings = {
        "formal": f"Good day, {name}. It is a pleasure to make your acquaintance.",
        "casual": f"Hey {name}, what's up?",
        "enthusiastic": f"OMG {name}!!! SO GREAT to see you!",
    }

    return {
        "greeting": greetings.get(style, greetings["casual"]),
        "style": style,
        "recipient": name,
    }


# ── Trigger (planelet webhook) ───────────────────────────────────────
# Triggers are external-service-driven: an outside system POSTs to a
# webhook URL. The trigger lifecycle has three phases:
#   1. setup   – called when the trigger is activated; register the
#                webhook URL with the external service
#   2. webhook – called on each incoming request; decide whether to
#                emit an event or skip
#   3. cleanup – called when the trigger is deactivated; tear down
#                the registration

new_quote = planelet.trigger(
    "new-quote",
    label="New Quote Received",
    description="Fires when an external service sends a new quote via webhook",
    parameters={
        "source": Param(
            label="Source",
            type="select",
            description="Which quote service to listen to",
            required=True,
            options=[
                ParamOption(label="QuoteBot", value="quotebot"),
                ParamOption(label="InspireAPI", value="inspireapi"),
            ],
        ),
    },
)


@new_quote.on_setup
async def setup_quote_webhook(ctx: SetupContext) -> dict:
    source = ctx.parameters["source"]
    print(f"Registering webhook {ctx.webhook.url} with {source}")
    return {"source": source, "registered": True}


@new_quote.on_webhook
async def handle_quote_webhook(ctx: WebhookContext) -> WebhookResult | WebhookSkip:
    body = json.loads(ctx.request.raw_body) if ctx.request.raw_body else {}

    if ctx.request.headers.get("x-webhook-secret"):
        secret = ctx.metadata.get("secret", "") if ctx.metadata else ""
        signature = ctx.request.headers["x-webhook-secret"][0]
        expected = hmac.new(
            secret.encode(), ctx.request.raw_body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return WebhookSkip(
                reason="Invalid signature",
                response=HttpResponse(status=401),
            )

    if not body.get("text"):
        return WebhookSkip(reason="No quote text in payload")

    return WebhookResult(
        event_type="quote.received",
        payload={
            "text": body["text"],
            "author": body.get("author", "Unknown"),
            "source": ctx.parameters.get("source", "unknown"),
        },
    )


@new_quote.on_cleanup
async def cleanup_quote_webhook(ctx: CleanupContext) -> None:
    source = ctx.metadata.get("source", "unknown") if ctx.metadata else "unknown"
    print(f"Unregistering webhook from {source}")


planelet.listen(3001)
