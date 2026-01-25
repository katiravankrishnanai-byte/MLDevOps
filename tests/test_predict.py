# tests/test_predict.py
import os
from fastapi.testclient import TestClient
from src.app import app

def test_predict():
    os.environ["MODEL_PATH"] = os.getenv("MODEL_PATH", "models/model.joblib")
    with TestClient(app) as client:
        payload = {
            "Acceleration": 5.0,
            "TopSpeed_KmH": 180,
            "Range_Km": 420,
            "Battery_kWh": 75,
            "Efficiency_WhKm": 170,
            "FastCharge_kW": 150,
            "Seats": 5,
            "PriceEuro": 45000,
            "PowerTrain": "AWD",
        }

        r = client.post("/predict", json=payload)
        assert r.status_code == 200
        body = r.json()
        assert "prediction" in body
        assert isinstance(body["prediction"], (int, float))
