from fastapi import FastAPI
from pydantic import BaseModel
import joblib
import numpy as np
import os

# -----------------------
# App init
# -----------------------
app = FastAPI(title="ML Prediction API")

# -----------------------
# Load model (once)
# -----------------------
MODEL_PATH = os.getenv("MODEL_PATH", "models/rf_component_bundle.joblib")

try:
    model = joblib.load(MODEL_PATH)
except Exception as e:
    raise RuntimeError(f"Failed to load model from {MODEL_PATH}: {e}")

# -----------------------
# Request schema (STRICT)
# -----------------------
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

# -----------------------
# Health check
# -----------------------
@app.get("/health")
def health():
    return {"status": "ok"}

# -----------------------
# Prediction endpoint
# -----------------------
@app.post("/predict")
def predict(req: PredictRequest):
    # Order MUST match training feature order
    features = np.array([[
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
    ]])

    prediction = model.predict(features)[0]

    return {
        "prediction": float(prediction)
    }
