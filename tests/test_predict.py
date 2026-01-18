from fastapi.testclient import TestClient
from src.app import app

client = TestClient(app)

def test_predict():
    payload = {
        "feature1": 1,
        "feature2": 2
    }

    response = client.post("/predict", json=payload)

    assert response.status_code == 200
    assert "prediction" in response.json()
    assert isinstance(response.json()["prediction"], float)
