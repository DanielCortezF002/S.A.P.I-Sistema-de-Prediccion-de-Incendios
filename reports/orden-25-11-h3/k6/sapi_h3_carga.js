// k6 · orden 25-11 · stack sapi-h3-518c0b5 (SHA 518c0b58e6b229317f51b1da56ac23346dc2ef74)
// PREPARADO, NO EJECUTADO. Cada corrida exige luz verde explícita del Director
// (hay sesión SUS de Daniel: no puede haber carga sin autorización).
// Ejecutado en el computador local, no en ambiente desplegado.
//
// Escenarios (uno por corrida, con -e ESCENARIO=...):
//   humo  : 1 VU, 5 iteraciones. Comprueba que el guion y los endpoints responden.
//   l1    : 2 VUs constantes, 3 min, GET /api/v1/ranking.
//   l2    : 5 VUs constantes, 3 min, GET /api/v1/ranking.
//   rampa : 0 -> 10 VUs en 2 min, 2 min sostenido, bajada en 30 s.
// Métricas medibles: http_req_duration p50/p95/p99 por endpoint, http_req_failed,
// checks (status 200, 50 celdas, score_semantics=relative_rank), iteraciones/s.
// Umbrales: propuestos y parametrizables (P95_MS, ERR_RATE). No son criterios
// adoptados del proyecto: deben fijarse antes de usarse como PASS/FAIL.

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend } from 'k6/metrics';

const BASE = __ENV.BASE_URL || 'http://host.docker.internal:18080';
const ESC = __ENV.ESCENARIO || 'humo';
const P95_MS = Number(__ENV.P95_MS || 10000);
const ERR_RATE = Number(__ENV.ERR_RATE || 0.01);
const PAUSA_S = Number(__ENV.PAUSA_S || 1);

// Barrera: nunca contra el stack 'sapi' (puertos 8080/8000/8501), salvo override explícito.
if (/:(8080|8000|8501)(\/|$)/.test(BASE) && __ENV.PERMITIR_STACK_SAPI !== 'si') {
  throw new Error(`BASE_URL ${BASE} apunta al stack 'sapi'. Abortado.`);
}

const escenarios = {
  humo: { executor: 'shared-iterations', vus: 1, iterations: 5, maxDuration: '3m' },
  l1: { executor: 'constant-vus', vus: 2, duration: '3m' },
  l2: { executor: 'constant-vus', vus: 5, duration: '3m' },
  rampa: {
    executor: 'ramping-vus', startVUs: 0,
    stages: [{ duration: '2m', target: 10 }, { duration: '2m', target: 10 }, { duration: '30s', target: 0 }],
    gracefulRampDown: '30s',
  },
};
if (!escenarios[ESC]) throw new Error(`ESCENARIO desconocido: ${ESC}`);

export const options = {
  scenarios: { [ESC]: escenarios[ESC] },
  summaryTrendStats: ['min', 'med', 'avg', 'p(90)', 'p(95)', 'p(99)', 'max', 'count'],
  thresholds: {
    'http_req_failed': [`rate<${ERR_RATE}`],
    'http_req_duration{endpoint:ranking}': [`p(95)<${P95_MS}`],
    'checks': ['rate>0.99'],
  },
  tags: { stack: 'sapi-h3-518c0b5', sha: '518c0b5' },
};

const rankingMs = new Trend('ranking_ms', true);

export default function () {
  if (ESC === 'humo') {
    const h = http.get(`${BASE}/health`, { tags: { endpoint: 'health' }, timeout: '20s' });
    check(h, { 'health 200': (r) => r.status === 200 });
  }
  const r = http.get(`${BASE}/api/v1/ranking`, { tags: { endpoint: 'ranking' }, timeout: '90s' });
  rankingMs.add(r.timings.duration);
  let body = null;
  try { body = r.json(); } catch (_) { body = null; }
  check(r, {
    'ranking 200': (x) => x.status === 200,
    'ranking 50 celdas': () => !!body && Array.isArray(body.cells) && body.cells.length === 50,
    'score_semantics relative_rank': () => !!body && body.score_semantics === 'relative_rank',
  });
  sleep(PAUSA_S);
}

export function handleSummary(data) {
  const out = __ENV.SALIDA || '/out/resumen.json';
  return { [out]: JSON.stringify(data, null, 2), stdout: `\nresumen en ${out}\n` };
}
