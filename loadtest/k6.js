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

const BASE_URL = __ENV.BASE_URL; // injected by Jenkins

export default function () {
  // Payload MUST match Assignment 2 input schema
  const payload = JSON.stringify({
    feature1: 1,
    feature2: 2
  });

  const params = {
    headers: {
      "Content-Type": "application/json",
    },
  };

  const res = http.post(`${BASE_URL}/predict`, payload, params);

  check(res, {
    "HTTP 200 returned": (r) => r.status === 200,
    "response has prediction": (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.prediction !== undefined;
      } catch (e) {
        return false;
      }
    },
  });

  sleep(0.2);
}
