import http from "k6/http";
import { check, sleep } from "k6";

/*
  Load profile:
  - Ramp up to moderate load
  - Hold
  - Ramp down
*/
export const options = {
  stages: [
    { duration: "20s", target: 10 },   // warm-up
    { duration: "40s", target: 30 },   // steady load
    { duration: "20s", target: 0 },    // ramp-down
  ],
  thresholds: {
    http_req_failed: ["rate<0.01"],     // <1% error rate
    http_req_duration: ["p(95)<800"],   // p95 latency < 800 ms
  },
};

const BASE_URL = (__ENV.BASE_URL && __ENV.BASE_URL.trim()) || "http://mldevops:8000";


export default function () {
  const payload = JSON.stringify({
    // Keep this ONLY if your API expects a numeric list
    features: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
  });

  const res = http.post(`${BASE_URL}/predict`, payload, {
    headers: { "Content-Type": "application/json" },
    timeout: "10s",
  });

  check(res, {
    "HTTP 200": (r) => r.status === 200,
    "json response": (r) => (r.headers["Content-Type"] || "").includes("application/json"),
    "has prediction": (r) => {
      try {
        const body = JSON.parse(r.body || "{}");
        return body.prediction !== undefined;
      } catch (e) {
        return false;
      }
    },
  });

  sleep(0.2);
}
