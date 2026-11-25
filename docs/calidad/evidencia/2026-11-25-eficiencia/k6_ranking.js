// C4 · Eficiencia · k6 contra GET /api/v1/ranking del stack sapi-h3-518c0b5.
// Declaración: docs/calidad/eficiencia-k6-2026-11-25.md (commiteada antes de correr).
// NO es KPI-03 (latencia visible en Edge, congelada).
// Ejecutado en el computador local, no en ambiente desplegado.
//
// FASE=calentamiento : 1 VU, 2 iteraciones secuenciales. Se guarda, no se mide.
// FASE=medicion      : 2 VUs constantes, 3 min, pausa 1 s entre iteraciones.
// Timeout por petición 90 s: el backend corta antes (read-timeout al ML 60 s -> 504),
// así que un timeout del ML cuenta como error, no se descarta.

import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE = __ENV.BASE_URL || 'http://host.docker.internal:18080';
const FASE = __ENV.FASE || '';
const SALIDA = __ENV.SALIDA || '/out/resumen.json';

// Barrera: solo el stack h3 (18080). Nunca el stack 'sapi'.
if (!/:18080(\/|$)/.test(BASE)) {
  throw new Error(`BASE_URL ${BASE} no es el backend de sapi-h3-518c0b5 (:18080). Abortado.`);
}

const fases = {
  calentamiento: { executor: 'shared-iterations', vus: 1, iterations: 2, maxDuration: '4m' },
  medicion: { executor: 'constant-vus', vus: 2, duration: '3m', gracefulStop: '90s' },
};
if (!fases[FASE]) throw new Error(`FASE desconocida: ${FASE}`);

export const options = {
  scenarios: { [FASE]: fases[FASE] },
  summaryTrendStats: ['min', 'med', 'avg', 'p(90)', 'p(95)', 'p(99)', 'max', 'count'],
  // Umbrales declarados (solo se leen en la fase de medición).
  thresholds: FASE === 'medicion'
    ? { 'http_req_duration{endpoint:ranking}': ['p(95)<=20000'], 'http_req_failed': ['rate<0.01'] }
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
  sleep(1);
}

export function handleSummary(data) {
  return { [SALIDA]: JSON.stringify(data, null, 2), stdout: `\nresumen en ${SALIDA}\n` };
}
