import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: 5,
  duration: '15s',
  thresholds: {
    http_req_failed: ['rate<0.05'],
    http_req_duration: ['p(95)<800'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://mldevops:8000';

export default function () {
  const h = http.get(`${BASE_URL}/health`);
  check(h, { 'health 200': (r) => r.status === 200 });

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

  const p = http.post(`${BASE_URL}/predict`, payload, {
    headers: { 'Content-Type': 'application/json' },
  });

  check(p, { 'predict 200': (r) => r.status === 200 });

  sleep(1);
}
