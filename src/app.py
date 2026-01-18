from pathlib import Path
import joblib
from fastapi import FastAPI, HTTPException

app = FastAPI()

MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "rf_component_bundle.joblib"
model = None

@app.on_event("startup")
def load_model():
    global model
    if not MODEL_PATH.exists():
        model = None
        return
    model = joblib.load(MODEL_PATH)

@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": model is not None}

@app.post("/predict")
def predict(data: dict):
    if model is None:
        raise HTTPException(status_code=500, detail="Model not loaded. Ensure models/rf_component_bundle.joblib exists.")
    X = list(data.values())
    y = model.predict([X])[0]
    return {"prediction": float(y)}
