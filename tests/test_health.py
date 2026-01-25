from fastapi.testclient import TestClient
from src.app import app

def test_health_endpoint():
    with TestClient(app) as client:
        res = client.get("/health")
        assert res.status_code == 200
        body = res.json()
        assert body["model_loaded"] is True
        assert body["status"] == "ok"
