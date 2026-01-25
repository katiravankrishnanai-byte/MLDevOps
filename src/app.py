import os
from pathlib import Path
from contextlib import asynccontextmanager

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException

# ---- Stable artifact resolution (works in pytest, uvicorn, container) ----
def _default_model_path() -> str:
    # <repo>/src/app.py -> <repo>/models/model.joblib
    repo_root = Path(__file__).resolve().parents[1]
    return str(repo_root / "models" / "model.joblib")

def _resolved_model_path() -> str:
    return os.getenv("MODEL_PATH", _default_model_path())

MODEL = None
MODEL_LOADED = False
MODEL_ERROR = None

# This must match your trained model features exactly
FEATURES = [
    "Acceleration",
    "TopSpeed_KmH",
    "Range_Km",
    "Battery_kWh",
    "Efficiency_WhKm",
    "FastCharge_kW",
    "Seats",
    "PriceEuro",
    "PowerTrain",
]

def _load_model() -> None:
    global MODEL, MODEL_LOADED, MODEL_ERROR
    path = _resolved_model_path()
    try:
        MODEL = joblib.load(path)
        MODEL_LOADED = True
        MODEL_ERROR = None
    except Exception as e:
        MODEL = None
        MODEL_LOADED = False
        MODEL_ERROR = f"{type(e).__name__}: {e}"

@asynccontextmanager
async def lifespan(_: FastAPI):
    _load_model()
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/health")
def health():
    status = "ok" if MODEL_LOADED else "degraded"
    return {
        "status": status,
        "model_loaded": MODEL_LOADED,
        "model_path": _resolved_model_path(),
        "error": MODEL_ERROR,
    }

@app.post("/predict")
def predict(payload: dict):
    if not MODEL_LOADED or MODEL is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    missing = [f for f in FEATURES if f not in payload]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required features: {missing}"
        )

    # Keep column order stable
    row = {f: payload[f] for f in FEATURES}
    X = pd.DataFrame([row], columns=FEATURES)

    try:
        yhat = MODEL.predict(X)
        pred = float(yhat[0])
        return {"prediction": pred}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {type(e).__name__}: {e}")
