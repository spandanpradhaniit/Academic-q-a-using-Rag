import asyncio

from fastapi import FastAPI
from fastapi.responses import Response
from redis.exceptions import ConnectionError as RedisConnectionError
from starlette.requests import Request

from app.core import rate_limit


class FakeRedis:
    def __init__(self):
        self.counts = {}

    async def eval(self, script, key_count, key, window_seconds):
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key], window_seconds


def _request(app):
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/api/auth/login",
            "raw_path": b"/api/auth/login",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
            "app": app,
        }
    )


def test_authentication_limit_returns_429_and_retry_after(monkeypatch):
    app = FastAPI()
    redis = FakeRedis()
    app.state.rate_limit_redis = redis
    monkeypatch.setattr(
        rate_limit,
        "get_settings",
        lambda: type("Settings", (), {"rate_limit_enabled": True})(),
    )

    async def call_next(request):
        return Response(status_code=200)

    async def make_requests():
        responses = []
        for _ in range(11):
            responses.append(await rate_limit.enforce_rate_limit(_request(app), call_next))
        return responses

    responses = asyncio.run(make_requests())
    assert all(response.status_code == 200 for response in responses[:10])
    assert responses[10].status_code == 429
    assert responses[10].headers["Retry-After"] == "60"


def test_rate_limit_fails_closed_when_redis_is_unavailable(monkeypatch):
    app = FastAPI()

    class UnavailableRedis:
        async def eval(self, *args):
            raise RedisConnectionError("redis offline")

    app.state.rate_limit_redis = UnavailableRedis()
    monkeypatch.setattr(
        rate_limit,
        "get_settings",
        lambda: type("Settings", (), {"rate_limit_enabled": True})(),
    )

    async def call_next(request):
        return Response(status_code=200)

    response = asyncio.run(rate_limit.enforce_rate_limit(_request(app), call_next))
    assert response.status_code == 503
    assert b"RATE_LIMITER_UNAVAILABLE" in response.body
