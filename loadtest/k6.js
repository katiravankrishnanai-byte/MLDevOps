import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://mldevops:8000";
const HEALTH_PATH = __ENV.HEALTH_PATH || "/health";
const PREDICT_PATH = __ENV.PREDICT_PATH || "/predict";

// This file must contain a VALID /predict payload for your FastAPI schema.
// Put the exact same JSON body you used in tests/test_predict.py into loadtest/request.json
const payload = open("/scripts/request.json");

export const options = {
  stages: [
    { duration: "10s", target: 5 },
    { duration: "40s", target: 30 },
    { duration: "30s", target: 0 },
  ],
  thresholds: {
    http_req_failed: ["rate<0.01"],     // must be <1% failed
    http_req_duration: ["p(95)<800"],   // keep your latency gate
  },
};

export default function () {
  // 1) health
  const h = http.get(`${BASE_URL}${HEALTH_PATH}`);
  check(h, {
    "health returns 200": (r) => r.status === 200,
  });

  // 2) predict
  const p = http.post(`${BASE_URL}${PREDICT_PATH}`, payload, {
    headers: { "Content-Type": "application/json" },
  });

  check(p, {
    "predict returns 200": (r) => r.status === 200,
    "predict returns json": (r) => {
      try { r.json(); return true; } catch (e) { return false; }
    },
    "predict has prediction field": (r) => {
      try {
        const j = r.json();
        return (
          j.prediction !== undefined ||
          j.predictions !== undefined ||
          j.result !== undefined ||
          j.eta !== undefined
        );
      } catch (e) {
        return false;
      }
    },
  });

  sleep(0.1);
}
