import os
from typing import Optional, Any, Dict, List

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


# -----------------------------
# Request schema (matches tests + smoke)
# -----------------------------
class PredictRequest(BaseModel):
    Acceleration: float
    TopSpeed_KmH: float
    Range_Km: float
    Battery_kWh: float
    Efficiency_WhKm: float
    FastCharge_kW: float
    Seats: float
    PriceEuro: float
    PowerTrain: str


# -----------------------------
# App + globals
# -----------------------------
app = FastAPI()

ARTIFACT: Optional[Any] = None
PIPELINE: Optional[Any] = None
CONTRACT: Dict[str, Any] = {}

MODEL_LOADED = False


def _is_preprocessor_present(obj: Any) -> bool:
    # Pipeline with preprocess usually has "transform" or a ColumnTransformer in steps.
    if hasattr(obj, "steps"):
        for _, step in getattr(obj, "steps", []):
            if hasattr(step, "transform"):
                return True
    return hasattr(obj, "transform")


def _feature_order() -> List[str]:
    # Prefer contract feature order if present.
    fo = CONTRACT.get("feature_order")
    if isinstance(fo, list) and len(fo) > 0:
        return fo

    # Next best: sklearn feature_names_in_
    if PIPELINE is not None and hasattr(PIPELINE, "feature_names_in_"):
        return list(getattr(PIPELINE, "feature_names_in_"))

    # Fallback: the 9 fields used in your tests/smoke payload.
    return [
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


@app.on_event("startup")
def load_artifact() -> None:
    global ARTIFACT, PIPELINE, CONTRACT, MODEL_LOADED

    model_path = os.getenv("MODEL_PATH", os.path.join("models", "model.joblib"))

    try:
        ARTIFACT = joblib.load(model_path)

        # Your repo’s artifact is a dict bundle in the stable version.
        if isinstance(ARTIFACT, dict):
            PIPELINE = (
                ARTIFACT.get("pipeline")
                or ARTIFACT.get("model")
                or ARTIFACT.get("estimator")
            )
            CONTRACT = ARTIFACT.get("contract") or {}
        else:
            PIPELINE = ARTIFACT
            CONTRACT = {}

        MODEL_LOADED = PIPELINE is not None
    except Exception:
        ARTIFACT = None
        PIPELINE = None
        CONTRACT = {}
        MODEL_LOADED = False


@app.get("/health")
def health(response: Response) -> Dict[str, Any]:
    ok = bool(MODEL_LOADED)
    if not ok:
        response.status_code = 503
    return {
        "status": "ok" if ok else "not_ready",
        "model_loaded": ok,
        "preprocessor_present": bool(
            PIPELINE is not None and _is_preprocessor_present(PIPELINE)
        ),
        "model_path": os.getenv("MODEL_PATH", os.path.join("models", "model.joblib")),
    }


@app.post("/predict")
def predict(req: PredictRequest) -> Dict[str, Any]:
    if not MODEL_LOADED or PIPELINE is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        payload = req.model_dump()
        cols = _feature_order()

        # Build 1-row DataFrame in correct column order
        row = {c: payload.get(c) for c in cols}
        X = pd.DataFrame([row], columns=cols)

        yhat = PIPELINE.predict(X)
        pred = float(yhat[0])

        return {"prediction": pred}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
