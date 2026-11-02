"""
HotelOS — High-Performance In-Memory Sliding Window Rate Limiter
Enforces request throttling and brute-force protection across sensitive endpoints.
Zero external infrastructure required (in-memory with automatic cleanup).
"""

import time
import asyncio
from collections import defaultdict
from typing import Callable, Optional
from fastapi import Request, HTTPException, status
from app.core.config import settings

class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int, scope: str = "default"):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.scope = scope
        # Maps key -> list of request timestamps (epoch floats)
        self._history = defaultdict(list)
        self._lock = None
        self._lock_loop = None
        self._last_cleanup = time.time()

    def _get_lock(self) -> asyncio.Lock:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if self._lock is None or self._lock_loop is not loop:
            self._lock = asyncio.Lock()
            self._lock_loop = loop
        return self._lock

    async def is_allowed(self, key: str) -> tuple[bool, int, int]:
        """
        Records attempt and checks if allowed within sliding window.
        Returns:
            (allowed: bool, current_count: int, retry_after: int)
        """
        now = time.time()
        window_start = now - self.window_seconds

        async with self._get_lock():
            # Periodic cleanup of expired keys every 60 seconds
            if now - self._last_cleanup > 60:
                self._cleanup(now)
                self._last_cleanup = now

            timestamps = self._history[key]
            # Prune timestamps older than window_start
            valid_timestamps = [t for t in timestamps if t > window_start]
            self._history[key] = valid_timestamps

            if len(valid_timestamps) >= self.max_requests:
                earliest_valid = valid_timestamps[0]
                retry_after = max(1, int(earliest_valid + self.window_seconds - now))
                return False, len(valid_timestamps), retry_after

            # Record this request
            self._history[key].append(now)
            return True, len(self._history[key]), 0

    async def check_only(self, key: str) -> tuple[bool, int, int]:
        """Checks if key is currently rate-limited without recording a new hit."""
        now = time.time()
        window_start = now - self.window_seconds

        async with self._get_lock():
            timestamps = self._history[key]
            valid_timestamps = [t for t in timestamps if t > window_start]
            self._history[key] = valid_timestamps

            if len(valid_timestamps) >= self.max_requests:
                earliest_valid = valid_timestamps[0]
                retry_after = max(1, int(earliest_valid + self.window_seconds - now))
                return False, len(valid_timestamps), retry_after
            return True, len(valid_timestamps), 0

    async def record_hit(self, key: str) -> None:
        """Records a timestamp for this key (e.g., on a failed authentication attempt)."""
        now = time.time()
        async with self._get_lock():
            self._history[key].append(now)

    async def reset_key(self, key: str) -> None:
        """Clears recorded hits for a specific key (e.g., after successful authentication)."""
        async with self._get_lock():
            if key in self._history:
                del self._history[key]

    def _cleanup(self, now: float):
        cutoff = now - self.window_seconds
        keys_to_remove = []
        for key, timestamps in self._history.items():
            fresh = [t for t in timestamps if t > cutoff]
            if fresh:
                self._history[key] = fresh
            else:
                keys_to_remove.append(key)
        for k in keys_to_remove:
            del self._history[k]

    def reset(self):
        """Reset history (useful for testing)."""
        self._history.clear()


# Pre-configured rate limiters
# Login & Register IP Throttling: 10 attempts per minute per IP
login_rate_limiter = SlidingWindowRateLimiter(max_requests=10, window_seconds=60, scope="auth_login_ip")
# Account-Level Brute Force Protection: 5 failed attempts per 15 minutes per normalized email
account_login_rate_limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=900, scope="auth_login_account")
# Digital Check-in details: 20 requests per minute per IP
digital_checkin_rate_limiter = SlidingWindowRateLimiter(max_requests=20, window_seconds=60, scope="digital_checkin")
# AI Assistant: 30 requests per minute per tenant/user
ai_chat_rate_limiter = SlidingWindowRateLimiter(max_requests=30, window_seconds=60, scope="ai_chat")


def get_client_ip(request: Request) -> str:
    """
    Extracts real client IP address with strict reverse-proxy trust validation.
    Never trusts X-Forwarded-For unless the direct connecting peer IP is in TRUSTED_PROXIES.
    """
    if not request.client:
        return "unknown"

    peer_ip = request.client.host

    is_trusted = (
        settings.TRUST_ALL_PROXIES or
        peer_ip in settings.TRUSTED_PROXIES or
        any(peer_ip == tp or peer_ip.startswith(tp) for tp in settings.TRUSTED_PROXIES)
    )

    if is_trusted:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ips = [ip.strip() for ip in forwarded.split(",") if ip.strip()]
            if ips:
                return ips[0]

    return peer_ip


def rate_limit_dependency(limiter: SlidingWindowRateLimiter, key_func: Callable[[Request], str] = get_client_ip):
    """FastAPI dependency for rate limiting."""
    async def dependency(request: Request):
        client_key = f"{limiter.scope}:{key_func(request)}"
        allowed, count, retry_after = await limiter.is_allowed(client_key)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Maximum {limiter.max_requests} requests per {limiter.window_seconds}s. Try again in {retry_after}s.",
                headers={"Retry-After": str(retry_after)}
            )
    return dependency
