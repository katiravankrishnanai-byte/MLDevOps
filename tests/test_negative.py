import importlib

from fastapi.testclient import TestClient


def _valid_payload():
    return {
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


def test_predict_missing_required_field_returns_422():
    from src.app import app

    client = TestClient(app)
    payload = _valid_payload()
    payload.pop("PowerTrain")

    r = client.post("/predict", json=payload)
    assert r.status_code == 422


def test_predict_type_mismatch_returns_422():
    from src.app import app

    client = TestClient(app)
    payload = _valid_payload()
    payload["Seats"] = "five"

    r = client.post("/predict", json=payload)
    assert r.status_code == 422


def test_predict_model_not_loaded_returns_503(monkeypatch):
    monkeypatch.setenv("MODEL_PATH", "models/does_not_exist.joblib")

    import src.app as app_module

    importlib.reload(app_module)

    client = TestClient(app_module.app)
    r = client.post("/predict", json=_valid_payload())

    assert r.status_code == 503
    assert "detail" in r.json()
