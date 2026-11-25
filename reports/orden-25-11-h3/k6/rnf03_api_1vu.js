// Prueba complementaria a nivel API (k6) · RNF-03 adaptado a GET /api/v1/ranking.
// Ejecutado en el computador local, no en ambiente desplegado. No es KPI-03.
// Parámetros (luz verde de Daniel 25-11 08:50 Chile, vía Director):
//   FASE=calentamiento : 1 VU, 1 iteración (excluida de las muestras).
//   FASE=medicion      : 1 VU, 30 iteraciones secuenciales (per-vu-iterations), sin pausa.
// Umbral: p95 <= 2000 ms (rango más cercano, calculado aparte desde las 30 muestras) y 0 % de fallos.
// Timeout por petición 90 s; un timeout o un no-200 es fallo y no se reemplaza.
import http from 'k6/http';
import { check } from 'k6';

const BASE = __ENV.BASE_URL || 'http://host.docker.internal:18080';
const FASE = __ENV.FASE || '';
if (!/:18080(\/|$)/.test(BASE)) throw new Error(`BASE_URL ${BASE} no es sapi-h3-518c0b5 (:18080). Abortado.`);
const fases = {
  calentamiento: { executor: 'per-vu-iterations', vus: 1, iterations: 1, maxDuration: '3m' },
  medicion: { executor: 'per-vu-iterations', vus: 1, iterations: 30, maxDuration: '40m' },
};
if (!fases[FASE]) throw new Error(`FASE desconocida: ${FASE}`);

export const options = {
  scenarios: { [FASE]: fases[FASE] },
  summaryTrendStats: ['min', 'med', 'avg', 'p(90)', 'p(95)', 'max', 'count'],
  thresholds: FASE === 'medicion'
    ? { 'http_req_duration{endpoint:ranking}': ['p(95)<=2000'], 'http_req_failed': ['rate<=0'] }
    : {},
  tags: { stack: 'sapi-h3-518c0b5', sha_codigo: '518c0b5', fase: FASE },
};

export default function () {
  const r = http.get(`${BASE}/api/v1/ranking`, { tags: { endpoint: 'ranking' }, timeout: '90s' });
  let body = null;
  try { body = r.json(); } catch (_) { body = null; }
  check(r, {
    'ranking 200': (x) => x.status === 200,
    'ranking 50 celdas': () => !!body && Array.isArray(body.cells) && body.cells.length === 50,
    'score_semantics relative_rank': () => !!body && body.score_semantics === 'relative_rank',
  });
}
