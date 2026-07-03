"""API-key auth + per-key rate limiting for the /v1 endpoints.

Configuration is by environment (12-factor, container-friendly):
  AIGOV_API_KEYS    comma-separated valid keys. UNSET => open dev mode
                    (a warning is logged once); SET => X-API-Key required.
  AIGOV_RATE_LIMIT  requests per minute per key (default 60, 0 = unlimited).

Honest limits: the rate limiter is in-process memory - correct for a single
container, NOT for horizontally scaled replicas. Scale-out needs a shared
store (Redis) or an API gateway in front; that boundary is deliberate, not
an oversight.
"""

from __future__ import annotations

import logging
import os
import secrets
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

logger = logging.getLogger("aigov.auth")

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_open_mode_warned = False


def _configured_keys() -> list[str]:
    raw = os.environ.get("AIGOV_API_KEYS", "")
    return [k.strip() for k in raw.split(",") if k.strip()]


class RateLimiter:
    """Sliding-window (60s) request counter per key, thread-safe."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int) -> None:
        if limit <= 0:
            return
        now = time.monotonic()
        with self._lock:
            window = self._hits[key]
            while window and now - window[0] > 60.0:
                window.popleft()
            if len(window) >= limit:
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded ({limit} requests/minute).",
                    headers={"Retry-After": "60"},
                )
            window.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


rate_limiter = RateLimiter()


def require_api_key(api_key: str | None = Security(_api_key_header)) -> str:
    """FastAPI dependency guarding /v1. Returns the caller identity."""
    global _open_mode_warned
    keys = _configured_keys()

    if not keys:
        if not _open_mode_warned:
            logger.warning(
                "AIGOV_API_KEYS is not set - API running in OPEN dev mode. "
                "Set it before exposing this service."
            )
            _open_mode_warned = True
        caller = "anonymous"
    else:
        if api_key is None:
            raise HTTPException(
                status_code=401,
                detail="Missing X-API-Key header.",
                headers={"WWW-Authenticate": "ApiKey"},
            )
        if not any(secrets.compare_digest(api_key, k) for k in keys):
            raise HTTPException(status_code=403, detail="Invalid API key.")
        caller = api_key

    limit = int(os.environ.get("AIGOV_RATE_LIMIT", "60"))
    rate_limiter.check(caller, limit)
    return caller
