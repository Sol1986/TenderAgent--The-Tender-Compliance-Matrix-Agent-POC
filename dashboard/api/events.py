"""SSE framing, replay, and heartbeats without raw graph state."""

import asyncio
from collections.abc import AsyncIterator
from time import monotonic

from .errors import DemoError
from .models import RunEvent
from .store import RunStore


def encode_event(event: RunEvent) -> str:
    """Frame named events; JSON escapes embedded newline characters safely."""
    return f"id: {event.event_id}\nevent: {event.type}\ndata: {event.model_dump_json()}\n\n"


async def stream_events(
    store: RunStore, run_id: str, after: int, heartbeat_seconds: float
) -> AsyncIterator[str]:
    """Replay retained events, follow live work, and end once terminal is sent."""
    heartbeat_at = monotonic()
    while True:
        try:
            events, terminal = store.replay(run_id, after)
        except DemoError:
            # A slow subscriber can outlive terminal retention. Close cleanly;
            # its next snapshot request supplies the structured RUN_NOT_FOUND.
            return
        for event in events:
            yield encode_event(event)
            after = event.event_id
            heartbeat_at = monotonic()
        if terminal:
            return
        if monotonic() - heartbeat_at >= heartbeat_seconds:
            yield ": heartbeat\n\n"
            heartbeat_at = monotonic()
        await asyncio.sleep(min(0.1, heartbeat_seconds))
