from __future__ import annotations

import hashlib
import logging

import jwt
from fastapi import Request
from fastapi.responses import JSONResponse
try:
    from redis.exceptions import RedisError
except ImportError:
    RedisError = Exception

from app.core.config import get_settings
from app.core.security import decode_access_token

logger = logging.getLogger(__name__)

_INCREMENT_WINDOW = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return {count, redis.call('TTL', KEYS[1])}
"""

_LIMITS = {
    ("POST", "/api/auth/login"): ("login", 10, 60, None),
    ("POST", "/api/auth/register"): ("register", 5, 3600, None),
    ("POST", "/api/documents/upload"): ("upload", 20, 3600, 60),
    ("POST", "/api/chat/ask"): ("chat", 30, 60, 90),
    ("POST", "/api/chat/ask/stream"): ("chat", 30, 60, 90),
    ("DELETE", "/api/auth/me"): ("account-delete", 3, 86400, 10),
}


def _request_user_id(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    try:
        subject = decode_access_token(token).get("sub")
    except (jwt.InvalidTokenError, RuntimeError):
        return None
    return subject if isinstance(subject, str) else None


async def _increment(redis_client, key: str, window_seconds: int) -> tuple[int, int]:
    count, ttl = await redis_client.eval(
        _INCREMENT_WINDOW,
        1,
        key,
        window_seconds,
    )
    return int(count), max(1, int(ttl))


async def enforce_rate_limit(request: Request, call_next):
    settings = get_settings()
    rule = _LIMITS.get((request.method, request.url.path))
    if not settings.rate_limit_enabled or rule is None or request.method == "OPTIONS":
        return await call_next(request)

    redis_client = getattr(request.app.state, "rate_limit_redis", None)
    if redis_client is None:
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "error": {
                    "code": "RATE_LIMITER_UNAVAILABLE",
                    "message": "The request protection service is unavailable.",
                },
            },
        )

    name, user_limit, window_seconds, ip_limit = rule
    client_ip = request.client.host if request.client else "unknown"
    user_id = _request_user_id(request)
    limits = []
    if user_id and ip_limit is not None:
        limits.append((f"rate:{name}:user:{user_id}", user_limit))
    limits.append(
        (
            f"rate:{name}:ip:{client_ip}",
            ip_limit if ip_limit is not None else user_limit,
        )
    )

    try:
        for key, limit in limits:
            digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
            count, retry_after = await _increment(
                redis_client,
                f"academic-qa:rate:{digest}",
                window_seconds,
            )
            if count > limit:
                return JSONResponse(
                    status_code=429,
                    headers={"Retry-After": str(retry_after)},
                    content={
                        "success": False,
                        "error": {
                            "code": "RATE_LIMITED",
                            "message": "Too many requests. Please try again later.",
                        },
                    },
                )
    except RedisError:
        logger.exception("Redis rate limiter request failed")
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "error": {
                    "code": "RATE_LIMITER_UNAVAILABLE",
                    "message": "The request protection service is unavailable.",
                },
            },
        )
    return await call_next(request)
