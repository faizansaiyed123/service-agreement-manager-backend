from collections import deque
from hashlib import sha256
from threading import Lock
from time import monotonic

from fastapi import Request

from app.core.errors import DomainError

_lock = Lock()
_attempts: dict[tuple[str, str, str], tuple[int, deque[float]]] = {}
_last_sweep = 0.0
_MAX_TRACKED_BUCKETS = 20_000
_EVICT_BUCKETS = 256


def enforce_rate_limit(
    request: Request,
    *,
    scope: str,
    limit: int,
    window_seconds: int,
    subject: str = "",
    by_ip: bool = True,
) -> None:
    """Apply a bounded per-process sliding-window limit to authentication endpoints.

    A subject-based bucket is shared across client IPs. Put a provider WAF/rate limiter
    in front of the service as well; this is defense in depth, not a distributed limiter.
    """
    global _last_sweep
    client_ip = request.client.host if request.client else "unknown"
    identity = client_ip if by_ip else "shared"
    subject_digest = sha256(subject.strip().lower().encode("utf-8")).hexdigest() if subject else "-"
    key = (scope, identity, subject_digest)
    now = monotonic()
    cutoff = now - window_seconds
    with _lock:
        stored = _attempts.get(key)
        if stored is None:
            if len(_attempts) >= _MAX_TRACKED_BUCKETS:
                # Bound memory when many unique network addresses/identifiers arrive.
                for _ in range(min(_EVICT_BUCKETS, len(_attempts))):
                    _attempts.pop(next(iter(_attempts)))
            attempts: deque[float] = deque()
            _attempts[key] = (window_seconds, attempts)
        else:
            _, attempts = stored
        while attempts and attempts[0] <= cutoff:
            attempts.popleft()
        if len(attempts) >= limit:
            raise DomainError(429, "rate_limit_exceeded", "Too many authentication attempts. Please wait and try again.")
        attempts.append(now)
        if now - _last_sweep >= 60:
            _last_sweep = now
            for old_key, (old_window, old_attempts) in list(_attempts.items()):
                old_cutoff = now - old_window
                while old_attempts and old_attempts[0] <= old_cutoff:
                    old_attempts.popleft()
                if not old_attempts:
                    _attempts.pop(old_key, None)


def clear_rate_limit_state() -> None:
    """Clear state between isolated tests; never call this in production code."""
    global _last_sweep
    with _lock:
        _attempts.clear()
        _last_sweep = 0.0
