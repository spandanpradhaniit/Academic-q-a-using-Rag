"""Tests for security headers middleware."""

from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import main
from app.core import rate_limit


def test_responses_include_security_headers():
    with TestClient(main.app) as client:
        response = client.get("/api/health")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert response.headers.get("X-XSS-Protection") == "1; mode=block"
        assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        csp = response.headers.get("Content-Security-Policy", "")
        assert "frame-ancestors" in csp
        assert "'unsafe-eval'" not in csp
        assert "max-age=" in response.headers.get("Strict-Transport-Security", "")
        assert "camera=()" in response.headers.get("Permissions-Policy", "")


def test_cors_preflight_allows_configured_origin(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")
    with TestClient(main.app) as client:
        response = client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        # CORS middleware handles preflight before BaseHTTPMiddleware, so
        # security headers are not injected on pure preflight responses.
        # We just verify CORS itself works.
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers


def test_cors_headers_are_added_to_rate_limit_responses(monkeypatch):
    class RateLimitedRedis:
        async def eval(self, *args):
            return 6, 60

    origin = main.settings.cors_origins.split(",")[0].strip()
    monkeypatch.setattr(
        rate_limit,
        "get_settings",
        lambda: SimpleNamespace(rate_limit_enabled=True),
    )
    main.app.state.rate_limit_redis = RateLimitedRedis()

    response = TestClient(main.app).post(
        "/api/auth/register",
        headers={"Origin": origin},
        json={},
    )

    assert response.status_code == 429
    assert response.headers.get("access-control-allow-origin") == origin
    assert response.headers.get("access-control-allow-credentials") == "true"
