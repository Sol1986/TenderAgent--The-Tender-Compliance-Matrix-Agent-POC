"""SSE framing and quiet-run heartbeat behavior."""

import asyncio

from dashboard.api.config import Settings
from dashboard.api.events import stream_events
from dashboard.api.models import ErrorInfo
from dashboard.api.store import RunStore


def test_heartbeat_then_terminal_closes() -> None:
    """A quiet provider call keeps SSE alive; failure then ends the iterator."""

    async def scenario() -> None:
        store = RunStore(Settings())
        run_id = store.create("test")[0].run_id
        stream = stream_events(store, run_id, 0, 0.01)
        assert await anext(stream) == ": heartbeat\n\n"
        store.finish(run_id, error=ErrorInfo(code="TEST", message="Safe message"))
        frame = await anext(stream)
        assert "id: 1\nevent: run.failed\ndata:" in frame
        assert frame.endswith("\n\n")
        assert [event async for event in stream] == []

    asyncio.run(scenario())
