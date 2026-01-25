import os
import joblib
from fastapi import FastAPI, HTTPException

app = FastAPI()

MODEL = None
MODEL_LOADED = False
MODEL_ERROR = None

MODEL_PATH = os.getenv("MODEL_PATH", "models/model.joblib")

@app.on_event("startup")
def load_model():
    global MODEL, MODEL_LOADED, MODEL_ERROR
    try:
        MODEL = joblib.load(MODEL_PATH)
        MODEL_LOADED = True
        MODEL_ERROR = None
    except Exception as e:
        MODEL = None
        MODEL_LOADED = False
        MODEL_ERROR = str(e)

@app.get("/health")
def health():
    return {
        "status": "ok" if MODEL_LOADED else "degraded",
        "model_loaded": MODEL_LOADED,
        "model_path": MODEL_PATH,
        "error": MODEL_ERROR if not MODEL_LOADED else None,
    }

@app.post("/predict")
def predict(data: dict):
    if not MODEL_LOADED or MODEL is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    try:
        features = [
            data["Acceleration"],
            data["TopSpeed_KmH"],
            data["Range_Km"],
            data["Efficiency_WhKm"],
            data["FastCharge_KmH"],
            data["RapidCharge"],
            data["PowerTrain"],
            data["PlugType"],
            data["BodyStyle"],
            data["Segment"],
        ]
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Missing key: {e}")

    prediction = MODEL.predict([features])
    return {"prediction": float(prediction[0])}
