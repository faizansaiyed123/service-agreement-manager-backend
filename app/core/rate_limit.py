from collections import deque
from hashlib import sha256
from threading import Lock
from time import monotonic, time
from uuid import uuid4

from fastapi import Request
from redis import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings
from app.core.errors import DomainError

_lock = Lock()
_attempts: dict[tuple[str, str, str], tuple[int, deque[float]]] = {}
_last_sweep = 0.0
_redis_client: Redis | None = None
_redis_lock = Lock()

_SLIDING_WINDOW_SCRIPT = """
local now = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]
redis.call("ZREMRANGEBYSCORE", KEYS[1], "-inf", now - window_ms)
local count = redis.call("ZCARD", KEYS[1])
if count >= limit then return 0 end
redis.call("ZADD", KEYS[1], now, member)
redis.call("PEXPIRE", KEYS[1], window_ms)
return 1
"""


def _shared_limit(key: str, *, limit: int, window_seconds: int) -> None:
    settings = get_settings()
    if not settings.redis_url:
        if settings.app_env.lower() == "production":
            raise DomainError(503, "rate_limiter_unavailable", "Authentication protection is temporarily unavailable")
        return _memory_limit(key, limit=limit, window_seconds=window_seconds)

    global _redis_client
    try:
        with _redis_lock:
            if _redis_client is None:
                _redis_client = Redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=1.5,
                    socket_timeout=1.5,
                    health_check_interval=30,
                )
            client = _redis_client
        allowed = client.eval(
            _SLIDING_WINDOW_SCRIPT,
            1,
            key,
            int(time() * 1000),
            window_seconds * 1000,
            limit,
            uuid4().hex,
        )
    except RedisError as exc:
        if settings.app_env.lower() == "production":
            raise DomainError(503, "rate_limiter_unavailable", "Authentication protection is temporarily unavailable") from exc
        return _memory_limit(key, limit=limit, window_seconds=window_seconds)
    if not allowed:
        raise DomainError(429, "rate_limit_exceeded", "Too many authentication attempts. Please wait and try again.")


def _memory_limit(key: str, *, limit: int, window_seconds: int) -> None:
    global _last_sweep
    now = monotonic()
    cutoff = now - window_seconds
    with _lock:
        stored = _attempts.get((key, "", ""))
        if stored is None:
            attempts: deque[float] = deque()
            _attempts[(key, "", "")] = (window_seconds, attempts)
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


def enforce_rate_limit(
    request: Request,
    *,
    scope: str,
    limit: int,
    window_seconds: int,
    subject: str = "",
    by_ip: bool = True,
) -> None:
    """Enforce a shared sliding-window limit in production and local limits in tests/dev.

    In production, Redis is mandatory and the limiter fails closed on Redis errors. The
    reverse proxy/WAF must still enforce edge limits, especially for request floods that
    should be rejected before reaching the application.
    """
    client_ip = request.client.host if request.client else "unknown"
    identity = client_ip if by_ip else "shared"
    subject_digest = sha256(subject.strip().lower().encode("utf-8")).hexdigest() if subject else "-"
    key = f"sam:ratelimit:{scope}:{identity}:{subject_digest}"
    _shared_limit(key, limit=limit, window_seconds=window_seconds)


def clear_rate_limit_state() -> None:
    """Clear in-memory limiter state between isolated tests; never call in production."""
    global _last_sweep, _redis_client
    with _lock:
        _attempts.clear()
        _last_sweep = 0.0
    with _redis_lock:
        if _redis_client is not None:
            _redis_client.close()
        _redis_client = None
