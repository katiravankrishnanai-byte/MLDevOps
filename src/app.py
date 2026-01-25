# src/app.py
import os
import joblib
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException

MODEL = None
MODEL_LOADED = False
MODEL_ERROR = None

def _load_model():
    global MODEL, MODEL_LOADED, MODEL_ERROR
    path = os.getenv("MODEL_PATH", "models/model.joblib")
    try:
        MODEL = joblib.load(path)
        MODEL_LOADED = True
        MODEL_ERROR = None
    except Exception as e:
        MODEL = None
        MODEL_LOADED = False
        MODEL_ERROR = f"{type(e).__name__}: {e}"

@asynccontextmanager
async def lifespan(app: FastAPI):
    _load_model()
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/health")
def health():
    return {
        "status": "ok" if MODEL_LOADED else "degraded",
        "model_loaded": MODEL_LOADED,
        "model_path": os.getenv("MODEL_PATH", "models/model.joblib"),
        "error": MODEL_ERROR,
    }

@app.post("/predict")
def predict(payload: dict):
    if not MODEL_LOADED or MODEL is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    required_keys = [
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
    missing = [k for k in required_keys if k not in payload]
    if missing:
        raise HTTPException(status_code=422, detail=f"Missing key(s): {missing}")

    try:
        # model expects single-row tabular input
        X = [[
            payload["Acceleration"],
            payload["TopSpeed_KmH"],
            payload["Range_Km"],
            payload["Battery_kWh"],
            payload["Efficiency_WhKm"],
            payload["FastCharge_kW"],
            payload["Seats"],
            payload["PriceEuro"],
            payload["PowerTrain"],
        ]]

        # Works for sklearn estimators and sklearn pipelines
        y = MODEL.predict(X)
        pred = float(y[0])
        return {"prediction": pred}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference error: {type(e).__name__}: {e}")
