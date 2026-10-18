"""Invoke synchronous and asynchronous trigger functions."""

from __future__ import annotations

import asyncio
import concurrent.futures
from typing import Any

_LOOP: asyncio.AbstractEventLoop | None = None


def get_event_loop() -> asyncio.AbstractEventLoop:
    """Return a process-wide event loop for async triggers."""
    global _LOOP
    if _LOOP is None or _LOOP.is_closed():
        _LOOP = asyncio.new_event_loop()
        asyncio.set_event_loop(_LOOP)
    return _LOOP


def invoke(func: Any, kwargs: dict[str, Any], *, is_async: bool) -> Any:
    """Call a sync or async function and return its result."""
    if not is_async:
        return func(**kwargs)

    loop = get_event_loop()
    if loop.is_running():
        # Nested call from within a running loop: use a worker thread with its own loop.
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, func(**kwargs)).result()
    return loop.run_until_complete(func(**kwargs))


def shutdown_runtime() -> None:
    """Close the shared event loop if present."""
    global _LOOP
    if _LOOP is not None and not _LOOP.is_closed():
        _LOOP.close()
    _LOOP = None
