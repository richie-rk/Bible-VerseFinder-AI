"""
In-process sliding-window rate limiting for the endpoints that cost money.

Each /search miss is an OpenAI embedding call and each /summarize an LLM
call, so both are limited per client IP. State lives in this process: with
several workers each one enforces its own window. Behind a reverse proxy,
start uvicorn with --proxy-headers (and --forwarded-allow-ips) so
request.client is the real caller rather than the proxy.
"""

import math
import threading
import time
from collections import deque

from fastapi import HTTPException, Request

# Idle clients are dropped every this many requests so the table doesn't
# keep an entry for every IP ever seen.
_SWEEP_EVERY = 1000


class RateLimiter:
    """FastAPI dependency allowing `limit` requests per client within
    `window_seconds`. A limit of 0 or less disables it."""

    def __init__(self, limit: int, window_seconds: float = 60.0) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        self._requests_since_sweep = 0

    def __call__(self, request: Request) -> None:
        if self.limit <= 0:
            return
        client = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window_start = now - self.window_seconds

        with self._lock:
            self._maybe_sweep(window_start)
            hits = self._hits.setdefault(client, deque())
            while hits and hits[0] <= window_start:
                hits.popleft()
            if len(hits) >= self.limit:
                retry_after = max(1, math.ceil(hits[0] - window_start))
                raise HTTPException(
                    status_code=429,
                    detail="Too many requests. Please wait a moment and try again.",
                    headers={"Retry-After": str(retry_after)},
                )
            hits.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
            self._requests_since_sweep = 0

    def _maybe_sweep(self, window_start: float) -> None:
        self._requests_since_sweep += 1
        if self._requests_since_sweep < _SWEEP_EVERY:
            return
        self._requests_since_sweep = 0
        idle = [client for client, hits in self._hits.items() if not hits or hits[-1] <= window_start]
        for client in idle:
            del self._hits[client]
