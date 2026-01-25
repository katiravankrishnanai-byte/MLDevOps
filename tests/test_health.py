# tests/test_health.py
import os
from fastapi.testclient import TestClient
from src.app import app

def test_health():
    os.environ["MODEL_PATH"] = os.getenv("MODEL_PATH", "models/model.joblib")
    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["model_loaded"] is True
