from fastapi.testclient import TestClient
from app import main
from app.core.config import get_settings

def test_register_duplicate_login_and_protected_me(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY","test-secret-for-unit-tests-at-least-32")
    get_settings.cache_clear()

def test_refresh_token_rotation_detects_reuse_and_revokes_family(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY","test-secret-for-unit-tests-at-least-32")
    monkeypatch.setenv("REFRESH_COOKIE_SECURE","false")
    monkeypatch.setenv("REFRESH_COOKIE_SAMESITE","lax")
    get_settings.cache_clear()
    with TestClient(main.app) as client:
        registered=client.post("/api/auth/register",json={"name":"Refresh User","email":"refresh@example.edu","password":"secure-passphrase"})
        assert registered.status_code==201
        assert "refresh_token" not in registered.json()
        old_refresh=client.cookies.get("academic_refresh")
        old_csrf=registered.json()["csrf_token"]
        assert old_refresh and old_csrf

        csrf_denied=client.post("/api/auth/refresh")
        assert csrf_denied.status_code==403
        rotated=client.post("/api/auth/refresh",headers={"X-CSRF-Token":old_csrf})
        assert rotated.status_code==200
        new_refresh=client.cookies.get("academic_refresh")
        new_csrf=rotated.json()["csrf_token"]
        assert new_refresh and new_refresh!=old_refresh

        client.cookies.set("academic_refresh",old_refresh,path="/api/auth")
        client.cookies.set("academic_csrf",old_csrf,path="/api/auth")
        replay=client.post(
            "/api/auth/refresh",
            headers={"X-CSRF-Token":old_csrf},
        )
        assert replay.status_code==401
        assert replay.json()["detail"]["code"]=="REFRESH_TOKEN_REUSE"

        client.cookies.set("academic_refresh",new_refresh,path="/api/auth")
        client.cookies.set("academic_csrf",new_csrf,path="/api/auth")
        revoked=client.post("/api/auth/refresh",headers={"X-CSRF-Token":new_csrf})
        assert revoked.status_code==401
    get_settings.cache_clear()

def test_logout_revokes_refresh_session(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY","test-secret-for-unit-tests-at-least-32")
    monkeypatch.setenv("REFRESH_COOKIE_SECURE","false")
    monkeypatch.setenv("REFRESH_COOKIE_SAMESITE","lax")
    get_settings.cache_clear()
    with TestClient(main.app) as client:
        registered=client.post("/api/auth/register",json={"name":"Logout User","email":"logout@example.edu","password":"secure-passphrase"})
        csrf=registered.json()["csrf_token"]
        response=client.post("/api/auth/logout",headers={"X-CSRF-Token":csrf})
        assert response.status_code==200
        assert response.json()["success"] is True
        denied=client.post("/api/auth/refresh",headers={"X-CSRF-Token":csrf})
        assert denied.status_code==401
    get_settings.cache_clear()
    with TestClient(main.app) as client:
        payload={"name":"A Student","email":"student@example.edu","password":"secure-passphrase"}
        registered=client.post("/api/auth/register",json=payload)
        assert registered.status_code==201
        token=registered.json()["access_token"]
        assert "password_hash" not in registered.json()["user"]
        assert client.post("/api/auth/register",json=payload).status_code==409
        assert client.post("/api/auth/login",json={"email":payload["email"],"password":payload["password"]}).status_code==200
        assert client.post("/api/auth/login",json={"email":payload["email"],"password":"wrong"}).status_code==401
        response=client.get("/api/auth/me",headers={"Authorization":f"Bearer {token}"})
        assert response.status_code==200 and response.json()["email"]==payload["email"]
        assert client.get("/api/auth/me").status_code==401
    get_settings.cache_clear()
