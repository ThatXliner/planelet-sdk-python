"""
Timer trigger — demonstrates the event-based trigger model.

The planelet starts a background loop on setup and pushes events directly
to SuperPlane via its HTTP API. No webhook URL is involved — this is the
"On Planelet Event" pattern (as opposed to "On Planelet Webhook").

Requires: pip install httpx

Usage:
  SUPERPLANE_BASE_URL=http://localhost:8080 \
  SUPERPLANE_INTEGRATION_ID=timer-demo \
  SUPERPLANE_TOKEN=... \
  python examples/timer_trigger.py
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone

import httpx

from planelet_sdk import (
    CleanupContext,
    Param,
    SetupContext,
    create_planelet,
)

SUPERPLANE_BASE_URL = os.environ.get("SUPERPLANE_BASE_URL", "http://localhost:8080")
SUPERPLANE_INTEGRATION_ID = os.environ.get("SUPERPLANE_INTEGRATION_ID", "timer-demo")
SUPERPLANE_TOKEN = os.environ.get("SUPERPLANE_TOKEN", "")

active_tasks: dict[str, asyncio.Task] = {}  # type: ignore[type-arg]


async def emit_event(event_type: str, payload: dict) -> None:
    url = f"{SUPERPLANE_BASE_URL.rstrip('/')}/api/v1/integrations/{SUPERPLANE_INTEGRATION_ID}/events"
    headers = {"content-type": "application/json"}
    if SUPERPLANE_TOKEN:
        headers["authorization"] = f"Bearer {SUPERPLANE_TOKEN}"

    async with httpx.AsyncClient() as client:
        await client.post(url, json={"eventType": event_type, "payload": payload}, headers=headers)


planelet = create_planelet(
    id="timer-demo",
    label="Timer Demo",
    icon="clock",
    description="Emits events on a recurring interval.",
)

timer = planelet.trigger(
    "timer",
    label="Timer",
    icon="clock",
    description="Emits a timer.tick event every N seconds.",
    parameters={
        "intervalSeconds": Param(
            label="Interval (seconds)",
            type="number",
            required=True,
            default=60,
        ),
    },
)


@timer.on_setup
async def setup(ctx: SetupContext) -> dict:
    interval = max(1, int(ctx.parameters.get("intervalSeconds", 60)))

    async def tick_loop() -> None:
        while True:
            await asyncio.sleep(interval)
            try:
                await emit_event(
                    "timer.tick",
                    {"tick": datetime.now(timezone.utc).isoformat()},
                )
            except Exception:
                pass

    task_id = str(id(ctx))
    task = asyncio.create_task(tick_loop())
    active_tasks[task_id] = task

    return {"taskId": task_id, "intervalSeconds": interval}


@timer.on_cleanup
async def cleanup(ctx: CleanupContext) -> None:
    task_id = ctx.metadata.get("taskId", "") if ctx.metadata else ""
    task = active_tasks.pop(str(task_id), None)
    if task:
        task.cancel()


planelet.listen(int(os.environ.get("PORT", "3012")))
