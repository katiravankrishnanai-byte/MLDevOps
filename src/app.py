from fastapi import FastAPI
import joblib

app = FastAPI()

model = None

@app.on_event("startup")
def load_model():
    global model
    model = joblib.load("models/rf_component_bundle.joblib")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/predict")
def predict(data: dict):
    # TEMPORARY dummy logic until real schema added
    X = list(data.values())
    pred = model.predict([X])
    return {"prediction": float(pred[0])}
