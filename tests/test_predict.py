# src/app.py  (predict endpoint)

from fastapi import FastAPI
from pydantic import BaseModel
import pandas as pd
import joblib

app = FastAPI()

MODEL_PATH = "models/model.joblib"
model = joblib.load(MODEL_PATH)

class PredictRequest(BaseModel):
    machine_age_days: float
    temperature_c: float
    pressure_kpa: float
    vibration_mm_s: float
    humidity_pct: float
    operator_experience_yrs: float
    shift: float
    material_grade: float
    line_speed_m_min: float
    inspection_interval_hrs: float

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/predict")
def predict(req: PredictRequest):
    # DataFrame required because your sklearn pipeline uses column names
    df = pd.DataFrame([req.model_dump()], columns=req.model_dump().keys())
    y = float(model.predict(df)[0])
    return {"prediction": y}
