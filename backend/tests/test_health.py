from fastapi.testclient import TestClient
from app import main

def test_health_endpoint_with_database():
    with TestClient(main.app) as client:
        response=client.get("/api/health")
        assert response.status_code==200
        assert response.json()=={"status":"healthy","database":"connected"}
