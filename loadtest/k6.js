import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://mldevops:8000";

export const options = {
  scenarios: {
    smoke: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "10s", target: 5 },
        { duration: "20s", target: 10 },
        { duration: "10s", target: 0 },
      ],
      gracefulRampDown: "5s",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<1000"],
    checks: ["rate>0.99"],
  },
};

function health() {
  const res = http.get(`${BASE_URL}/health`, { timeout: "10s" });
  check(res, {
    "health status 200": (r) => r.status === 200,
    "health body ok": (r) => (r.body || "").includes("ok"),
  });
}

function predict() {
  // Adjust payload to match your FastAPI schema if needed.
  const payload = JSON.stringify({
    features: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
  });

  const params = {
    headers: { "Content-Type": "application/json" },
    timeout: "15s",
  };

  const res = http.post(`${BASE_URL}/predict`, payload, params);

  // If your API does not have /predict yet, keep this but allow 404 to show clearly in logs.
  check(res, {
    "predict status 200": (r) => r.status === 200,
  });
}

export default function () {
  health();
  predict();
  sleep(1);
}
