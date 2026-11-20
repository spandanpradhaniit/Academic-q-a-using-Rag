"""Tests for security headers middleware."""

from fastapi.testclient import TestClient

from app import main


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
