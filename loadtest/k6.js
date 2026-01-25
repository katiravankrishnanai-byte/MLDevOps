// loadtest/k6.js
import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  stages: [
    { duration: "20s", target: 10 },
    { duration: "40s", target: 30 },
    { duration: "20s", target: 0 },
  ],
};

const BASE_URL = __ENV.BASE_URL || "http://mldevops:8000";

export default function () {
  const payload = JSON.stringify({
    Acceleration: 5.0,
    TopSpeed_KmH: 180,
    Range_Km: 420,
    Battery_kWh: 75,
    Efficiency_WhKm: 170,
    FastCharge_kW: 150,
    Seats: 5,
    PriceEuro: 45000,
    PowerTrain: "AWD",
  });

  const params = { headers: { "Content-Type": "application/json" } };

  const r = http.post(`${BASE_URL}/predict`, payload, params);

  check(r, {
    "status is 200": (res) => res.status === 200,
    "has prediction": (res) => {
      try {
        const b = res.json();
        return b && typeof b.prediction === "number";
      } catch (e) {
        return false;
      }
    },
  });

  sleep(1);
}
