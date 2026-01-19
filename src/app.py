from fastapi import FastAPI
from pydantic import BaseModel
import numpy as np
import joblib
import os

app = FastAPI()

MODEL_PATH = os.getenv("MODEL_PATH", "models/model.joblib")

_bundle = joblib.load(MODEL_PATH)

# Support both: raw sklearn model OR dict bundle
if isinstance(_bundle, dict):
    model = _bundle.get("model") or _bundle.get("estimator") or _bundle.get("pipeline")
    feature_order = (
        _bundle.get("feature_order")
        or _bundle.get("feature_names")
        or _bundle.get("features")
    )
else:
    model = _bundle
    feature_order = None

if model is None:
    raise RuntimeError("Loaded model bundle is a dict but no 'model/estimator/pipeline' key found.")

class PredictRequest(BaseModel):
    machine_age_days: int
    temperature_c: float
    pressure_kpa: float
    vibration_mm_s: float
    humidity_pct: float
    operator_experience_yrs: int
    shift: int
    material_grade: int
    line_speed_m_min: float
    inspection_interval_hrs: float

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/predict")
def predict(req: PredictRequest):
    # If your training feature order differs, set it in the bundle and use it here.
    x = np.array([[
        req.machine_age_days,
        req.temperature_c,
        req.pressure_kpa,
        req.vibration_mm_s,
        req.humidity_pct,
        req.operator_experience_yrs,
        req.shift,
        req.material_grade,
        req.line_speed_m_min,
        req.inspection_interval_hrs,
    ]], dtype=float)

    y = float(model.predict(x)[0])
    return {"prediction": y}
