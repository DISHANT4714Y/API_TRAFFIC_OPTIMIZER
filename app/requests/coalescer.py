"""
Phase 8 — Request Coalescer.

Prevents duplicate simultaneous upstream API calls for identical in-flight
requests.  When multiple concurrent requests share the same cache key and
the cache is empty, only the first request calls the upstream; all others
await the same asyncio.Future and receive the identical result.

Design notes:
  - Uses asyncio.Lock to safely read/write the _in_flight dict.
  - Each in-flight slot is a plain asyncio.Future; waiters simply await it.
  - The driving coroutine sets result OR exception on the Future so waiters
    are always unblocked, even when the upstream call fails.
  - The slot is removed from _in_flight before the result is propagated so
    subsequent requests (after the current batch resolves) start fresh.
  - Different cache keys never share a Future; they run fully independently.
"""

import asyncio
import logging
from typing import Any, Callable, Coroutine, Dict

logger = logging.getLogger(__name__)


class RequestCoalescer:
    """
    Coalesces concurrent identical requests into a single upstream fetch.

    Usage::

        coalescer = RequestCoalescer()

        # Inside an async route handler:
        result = await coalescer.coalesce(
            key=cache_key,
            coro_factory=lambda: proxy_client.fetch_resource(resource_id),
        )
    """

    def __init__(self) -> None:
        self._in_flight: Dict[str, asyncio.Future] = {}
        self._lock: asyncio.Lock = asyncio.Lock()

    async def coalesce(
        self,
        key: str,
        coro_factory: Callable[[], Coroutine[Any, Any, Any]],
    ) -> Any:
        """
        Execute ``coro_factory()`` exactly once per unique *key* across any
        number of concurrent callers that arrive while the first call is
        still in progress.

        Args:
            key:          Unique identifier for this request (cache key).
            coro_factory: Zero-argument callable that returns a coroutine
                          performing the actual upstream fetch.

        Returns:
            The result returned by ``coro_factory()``.

        Raises:
            Whatever exception ``coro_factory()`` raises.  All concurrent
            waiters for the same *key* will receive the same exception.
        """
        async with self._lock:
            if key in self._in_flight:
                # Another coroutine is already fetching this key — wait for it
                future = self._in_flight[key]
                is_leader = False
            else:
                # We are the leader — create a Future that waiters will await
                loop = asyncio.get_running_loop()
                future = loop.create_future()
                self._in_flight[key] = future
                is_leader = True

        if not is_leader:
            logger.debug("[COALESCE] Waiting for in-flight request: key=%s", key[:32])
            return await asyncio.shield(future)

        # Leader: perform the upstream call
        logger.debug("[COALESCE] Leading upstream fetch: key=%s", key[:32])
        try:
            result = await coro_factory()
            # Unblock all waiters with the successful result
            async with self._lock:
                self._in_flight.pop(key, None)
            future.set_result(result)
            return result
        except Exception as exc:
            # Unblock all waiters with the exception so they don't hang.
            async with self._lock:
                self._in_flight.pop(key, None)
            future.set_exception(exc)
            # Mark the exception as retrieved so asyncio does not emit
            # "Future exception was never retrieved" in its __del__ warning
            # when there are no concurrent waiters for this key.
            # Waiters that are present will still receive the exception via
            # asyncio.shield(future) above; their own await retrieves it.
            future.exception()
            raise

