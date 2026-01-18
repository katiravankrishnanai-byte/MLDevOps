import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  stages: [
    { duration: "20s", target: 10 },
    { duration: "40s", target: 30 },
    { duration: "20s", target: 0 },
  ],
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<800"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://mldevops:8000";

export default function () {
  const payload = JSON.stringify({
    // MUST match your FastAPI /predict request model
    // example only:
    features: [1, 2, 3, 4,5,6,7,8,9,10],
  });

  const res = http.post(`${BASE_URL}/predict`, payload, {
    headers: { "Content-Type": "application/json" },
  });

  check(res, {
    "HTTP 200": (r) => r.status === 200,
    "json response": (r) => {
      try { r.json(); return true; } catch (e) { return false; }
    },
    "has prediction": (r) => {
      try {
        const j = r.json();
        return j.prediction !== undefined || j.result !== undefined;
      } catch (e) {
        return false;
      }
    },
  });

  sleep(0.2);
}
