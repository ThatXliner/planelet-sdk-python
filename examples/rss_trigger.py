"""
RSS feed trigger — demonstrates the event-based trigger model with polling.

Polls an RSS or Atom feed on an interval, tracks seen entries, and emits
events for new items via the SuperPlane event API.

Requires: pip install httpx

Usage:
  SUPERPLANE_BASE_URL=http://localhost:8080 \
  SUPERPLANE_INTEGRATION_ID=rss-demo \
  SUPERPLANE_TOKEN=... \
  python examples/rss_trigger.py
"""

from __future__ import annotations

import asyncio
import os
from xml.etree import ElementTree

import httpx

from planelet_sdk import (
    CleanupContext,
    Param,
    SetupContext,
    create_planelet,
)

SUPERPLANE_BASE_URL = os.environ.get("SUPERPLANE_BASE_URL", "http://localhost:8080")
SUPERPLANE_INTEGRATION_ID = os.environ.get("SUPERPLANE_INTEGRATION_ID", "rss-demo")
SUPERPLANE_TOKEN = os.environ.get("SUPERPLANE_TOKEN", "")

active_tasks: dict[str, asyncio.Task] = {}  # type: ignore[type-arg]


async def emit_event(event_type: str, payload: dict) -> None:
    url = f"{SUPERPLANE_BASE_URL.rstrip('/')}/api/v1/integrations/{SUPERPLANE_INTEGRATION_ID}/events"
    headers = {"content-type": "application/json"}
    if SUPERPLANE_TOKEN:
        headers["authorization"] = f"Bearer {SUPERPLANE_TOKEN}"

    async with httpx.AsyncClient() as client:
        await client.post(url, json={"eventType": event_type, "payload": payload}, headers=headers)


# ── Feed parsing ───────────────────────────────────────────────────

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


def parse_feed(xml_text: str) -> list[dict[str, str]]:
    root = ElementTree.fromstring(xml_text)

    if root.tag == "{http://www.w3.org/2005/Atom}feed" or root.tag == "feed":
        return _parse_atom(root)

    channel = root.find("channel")
    if channel is not None:
        return _parse_rss(channel)

    return []


def _parse_atom(root: ElementTree.Element) -> list[dict[str, str]]:
    entries = []
    for entry in root.findall("atom:entry", ATOM_NS) or root.findall("entry"):
        entry_id = _text(entry, "atom:id", ATOM_NS) or _text(entry, "id")
        title = _text(entry, "atom:title", ATOM_NS) or _text(entry, "title")

        link_el = entry.find("atom:link[@rel='alternate']", ATOM_NS)
        if link_el is None:
            link_el = entry.find("atom:link", ATOM_NS) or entry.find("link")
        link = link_el.get("href", "") if link_el is not None else ""

        published = (
            _text(entry, "atom:published", ATOM_NS)
            or _text(entry, "atom:updated", ATOM_NS)
            or _text(entry, "published")
            or _text(entry, "updated")
            or ""
        )

        if entry_id or link:
            entries.append({"id": entry_id or link, "title": title, "link": link, "published": published})
    return entries


def _parse_rss(channel: ElementTree.Element) -> list[dict[str, str]]:
    items = []
    for item in channel.findall("item"):
        title = _text(item, "title") or ""
        link = _text(item, "link") or ""
        guid = _text(item, "guid") or ""
        pub_date = _text(item, "pubDate") or ""

        if guid or link:
            items.append({"id": guid or link, "title": title, "link": link, "published": pub_date})
    return items


def _text(el: ElementTree.Element, path: str, namespaces: dict[str, str] | None = None) -> str:
    child = el.find(path, namespaces) if namespaces else el.find(path)
    return (child.text or "").strip() if child is not None else ""


# ── Planelet ───────────────────────────────────────────────────────

planelet = create_planelet(
    id="rss-demo",
    label="RSS Feed Monitor",
    icon="rss",
    description="Polls RSS/Atom feeds and emits events for new entries.",
)

rss_feed = planelet.trigger(
    "rss-feed",
    label="RSS Feed",
    icon="rss",
    description="Polls a feed URL and emits rss.newEntry for each new item.",
    parameters={
        "feedUrl": Param(
            label="Feed URL",
            type="string",
            required=True,
        ),
        "pollIntervalSeconds": Param(
            label="Poll Interval (seconds)",
            type="number",
            default=300,
        ),
    },
)


@rss_feed.on_setup
async def setup(ctx: SetupContext) -> dict:
    feed_url = str(ctx.parameters.get("feedUrl", "https://blog.cloudflare.com/rss/"))
    poll_interval = max(10, int(ctx.parameters.get("pollIntervalSeconds", 300)))

    seen_ids: set[str] = set()

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(feed_url)
            if resp.status_code == 200:
                for entry in parse_feed(resp.text):
                    seen_ids.add(entry["id"])
    except Exception:
        pass

    async def poll_loop() -> None:
        while True:
            await asyncio.sleep(poll_interval)
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(feed_url)
                    if resp.status_code != 200:
                        continue

                for entry in parse_feed(resp.text):
                    if entry["id"] in seen_ids:
                        continue
                    seen_ids.add(entry["id"])
                    await emit_event("rss.newEntry", {"feedUrl": feed_url, "entry": entry})
            except Exception:
                pass

    task_id = str(id(ctx))
    task = asyncio.create_task(poll_loop())
    active_tasks[task_id] = task

    return {
        "taskId": task_id,
        "feedUrl": feed_url,
        "pollIntervalSeconds": poll_interval,
        "initialEntries": len(seen_ids),
    }


@rss_feed.on_cleanup
async def cleanup(ctx: CleanupContext) -> None:
    task_id = ctx.metadata.get("taskId", "") if ctx.metadata else ""
    task = active_tasks.pop(str(task_id), None)
    if task:
        task.cancel()


planelet.listen(int(os.environ.get("PORT", "3013")))
