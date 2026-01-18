import http from "k6/http";
import { check, sleep } from "k6";

/*
  k6.js (Kubernetes-friendly)
  - Uses BASE_URL env var (set in Job): e.g. http://mldevops:8000
  - Tries /health then /predict (POST) by default
  - Fails the run only if failure-rate or latency crosses thresholds
*/

const BASE_URL = (__ENV.BASE_URL || "http://mldevops:8000");
const HEALTH_PATH = __ENV.HEALTH_PATH || "/health";
const PREDICT_PATH = __ENV.PREDICT_PATH || "/predict";

export const options = {
  stages: [
    { duration: "10s", target: 5 },
    { duration: "60s", target: 30 },
    { duration: "10s", target: 0 },
  ],
  thresholds: {
    http_req_failed: ["rate<0.01"],     // <1% requests fail
    http_req_duration: ["p(95)<800"],   // 95% under 800ms
    checks: ["rate>0.99"],              // >99% checks pass
  },
};

function url(path) {
  if (!path.startsWith("/")) path = `/${path}`;
  return `${BASE_URL}${path}`;
}

export default function () {
  // 1) Health check (GET)
  const h = http.get(url(HEALTH_PATH), {
    tags: { name: "health" },
    timeout: "10s",
  });

  const healthOk = check(h, {
    "health: HTTP 200": (r) => r.status === 200,
  });

  // If health is down, skip predict to avoid spamming a dead service
  if (!healthOk) {
    sleep(1);
    return;
  }

  // 2) Predict (POST)
  // Adjust payload to match your API contract.
  // This is a generic schema; update keys as your /predict expects.
  const payload = JSON.stringify({
    instances: [
      {
        Temperature: 10,
        Humidity: 50,
        Wind_speed: 2,
        Visibility: 2000,
        Dew_point_temperature: 3,
        Solar_Radiation: 0.1,
        Rainfall: 0,
        Snowfall: 0,
        Seasons: "Winter",
        Holiday: "No Holiday",
        Functioning_Day: "Yes",
        Hour: 12,
        Month: 1,
      },
    ],
  });

  const p = http.post(url(PREDICT_PATH), payload, {
    headers: { "Content-Type": "application/json" },
    tags: { name: "predict" },
    timeout: "10s",
  });

  check(p, {
    "predict: HTTP 200": (r) => r.status === 200,
    "predict: json": (r) => {
      try {
        r.json();
        return true;
      } catch (e) {
        return false;
      }
    },
    // Flexible: accept either {"prediction": ...} or {"predictions": [...]}
    "predict: has output field": (r) => {
      try {
        const j = r.json();
        return (
          (j && Object.prototype.hasOwnProperty.call(j, "prediction")) ||
          (j && Object.prototype.hasOwnProperty.call(j, "predictions")) ||
          (j && Object.prototype.hasOwnProperty.call(j, "result")) ||
          (j && Object.prototype.hasOwnProperty.call(j, "outputs"))
        );
      } catch (e) {
        return false;
      }
    },
  });

  sleep(0.2);
}
