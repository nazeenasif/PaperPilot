"""Run a blocking engine call on a worker thread and stream its callbacks as events.

The engine is synchronous; its progress callbacks fire on the worker thread and are handed to
the event loop with call_soon_threadsafe (research R3).
"""

import asyncio
from collections.abc import AsyncIterator, Callable
from typing import Any

Emit = Callable[[str, dict], None]


async def run_streaming(work: Callable[[Emit], Any], on_finished: Callable[[], None]) -> AsyncIterator[tuple]:
    """Yield ("event", kind, detail) items while `work(emit)` runs, then ("result", value) or
    ("error", exception). `on_finished` runs on the worker thread when the work ends, even if
    the client has gone away."""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[tuple] = asyncio.Queue()

    def put(item: tuple) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, item)

    def run() -> None:
        try:
            put(("result", work(lambda kind, detail: put(("event", kind, detail)))))
        except Exception as error:  # reported to the client as an error event
            put(("error", error))
        finally:
            on_finished()

    loop.run_in_executor(None, run)
    while True:
        item = await queue.get()
        yield item
        if item[0] != "event":
            return
