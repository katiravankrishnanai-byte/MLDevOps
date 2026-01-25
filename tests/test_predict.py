from fastapi.testclient import TestClient
from src.app import app

def test_predict_endpoint():
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
        res = client.post("/predict", json=payload)
        assert res.status_code == 200
        body = res.json()
        assert "prediction" in body
