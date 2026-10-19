"""Tiny in-memory sliding-window rate limiter used against brute force.

It lives in process memory, so with several worker processes each one keeps its own counters.
For a multi-worker deployment swap this class for a Redis-backed one (same four methods).
"""
import threading
import time
from collections import defaultdict, deque

from .exceptions import AppError


class RateLimiter:
    def __init__(self, max_hits: int, window_seconds: int, message: str):
        self.max_hits = max_hits
        self.window = window_seconds
        self.message = message
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, q: deque, now: float) -> None:
        while q and now - q[0] > self.window:
            q.popleft()

    def check(self, key: str) -> None:
        """Raise HTTP 429 if `key` already used up its allowance."""
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            self._prune(q, now)
            if len(q) >= self.max_hits:
                wait = max(1, int(self.window - (now - q[0])))
                raise AppError(429, f"{self.message} Try again in {wait} seconds.",
                               code="rate_limited", headers={"Retry-After": str(wait)})

    def hit(self, key: str) -> None:
        """Record one (failed) attempt."""
        with self._lock:
            self._hits[key].append(time.monotonic())

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()


login_limiter = RateLimiter(5, 10 * 60, "Too many failed log-in attempts.")
twofa_limiter = RateLimiter(5, 10 * 60, "Too many wrong codes.")
forgot_limiter = RateLimiter(3, 15 * 60, "Too many reset requests.")
reset_limiter = RateLimiter(8, 15 * 60, "Too many reset attempts.")
register_limiter = RateLimiter(10, 60 * 60, "Too many accounts created from this address.")
ALL_LIMITERS = (login_limiter, twofa_limiter, forgot_limiter, reset_limiter, register_limiter)
