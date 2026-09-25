// Conservative pilot policy. Pure functions; no I/O, credentials or delivery.
// This is an operational filter, not a scientific probability threshold.
//
// Notification identity: there is ONE canonical identity, `alert_identity.alert_fingerprint`
// from the bridge (sapi-output-v1), computed by src/notifications/alert_payload.py.
// This policy never invents another one: it recomputes the same recipe from the payload
// content (alertFingerprint below) and blocks when the identity is missing or does not match.
// Non-ranking outcomes use the non-ready recipe of alert_payload (_non_ready).

const ALERT_SCHEMA = 'sapi-alert-v1';
const OUTPUT_SCHEMA = 'sapi-output-v1';

// --- Canonical JSON identical to Python json.dumps(sort_keys=True, separators=(',', ':'),
// ensure_ascii=False). Scores are Python floats: JSON cannot tell 1 from 1.0, so they are
// wrapped and printed with Python's float repr.
class PyFloat { constructor(value) { this.value = value; } }
function pyFloatRepr(x) {
  if (!Number.isFinite(x)) throw new Error('non-finite float');
  if (Object.is(x, -0)) return '-0.0';
  if (Number.isInteger(x) && Math.abs(x) < 1e16) return String(x) + '.0';
  const [mantissa, exp] = x.toExponential().split('e');
  const e = Number(exp);
  if (e < -4 || e >= 16) return `${mantissa}e${e < 0 ? '-' : '+'}${String(Math.abs(e)).padStart(2, '0')}`;
  return String(x);
}
function canonicalJson(v) {
  if (v instanceof PyFloat) return pyFloatRepr(v.value);
  if (v === null) return 'null';
  if (Array.isArray(v)) return '[' + v.map(canonicalJson).join(',') + ']';
  if (typeof v === 'object') {
    return '{' + Object.keys(v).sort().map(k => JSON.stringify(k) + ':' + canonicalJson(v[k])).join(',') + '}';
  }
  if (typeof v === 'number') {
    if (!Number.isInteger(v)) throw new Error('floats must be PyFloat');
    return String(v);
  }
  return JSON.stringify(v);
}

// --- SHA-256 (FIPS 180-4) over UTF-8, dependency-free for the n8n Code sandbox.
function utf8Bytes(s) {
  const out = [];
  for (const ch of s) {
    const c = ch.codePointAt(0);
    if (c < 0x80) out.push(c);
    else if (c < 0x800) out.push(0xc0 | (c >> 6), 0x80 | (c & 63));
    else if (c < 0x10000) out.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63));
    else out.push(0xf0 | (c >> 18), 0x80 | ((c >> 12) & 63), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63));
  }
  return out;
}
const K = [0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4,
  0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7,
  0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc,
  0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351,
  0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e,
  0x92722c85, 0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585,
  0x106aa070, 0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f,
  0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7,
  0xc67178f2];
function sha256Hex(text) {
  const bytes = utf8Bytes(text);
  const bitLen = bytes.length * 8;
  bytes.push(0x80);
  while (bytes.length % 64 !== 56) bytes.push(0);
  const hi = Math.floor(bitLen / 0x100000000), lo = bitLen >>> 0;
  for (const word of [hi, lo]) bytes.push((word >>> 24) & 0xff, (word >>> 16) & 0xff, (word >>> 8) & 0xff, word & 0xff);
  const h = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19];
  const w = new Array(64);
  const rotr = (x, n) => (x >>> n) | (x << (32 - n));
  for (let off = 0; off < bytes.length; off += 64) {
    for (let i = 0; i < 16; i++) {
      w[i] = (bytes[off + 4 * i] << 24) | (bytes[off + 4 * i + 1] << 16) | (bytes[off + 4 * i + 2] << 8) | bytes[off + 4 * i + 3];
    }
    for (let i = 16; i < 64; i++) {
      const s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >>> 3);
      const s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >>> 10);
      w[i] = (w[i - 16] + s0 + w[i - 7] + s1) | 0;
    }
    let [a, b, c, d, e, f, g, hh] = h;
    for (let i = 0; i < 64; i++) {
      const t1 = (hh + (rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)) + ((e & f) ^ (~e & g)) + K[i] + w[i]) | 0;
      const t2 = ((rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)) + ((a & b) ^ (a & c) ^ (b & c))) | 0;
      hh = g; g = f; f = e; e = (d + t1) | 0; d = c; c = b; b = a; a = (t1 + t2) | 0;
    }
    h[0] = (h[0] + a) | 0; h[1] = (h[1] + b) | 0; h[2] = (h[2] + c) | 0; h[3] = (h[3] + d) | 0;
    h[4] = (h[4] + e) | 0; h[5] = (h[5] + f) | 0; h[6] = (h[6] + g) | 0; h[7] = (h[7] + hh) | 0;
  }
  return h.map(x => (x >>> 0).toString(16).padStart(8, '0')).join('');
}

// --- The single alert identity recipe (mirror of alert_payload.build_alert).
function alertFingerprint(p, topN) {
  const model = {};
  if (p.model_version != null) model.version = p.model_version;
  if (p.model_status != null) model.status = p.model_status;
  const shown = [...p.cells].sort((a, b) => a.rank - b.rank).slice(0, topN);
  return sha256Hex(canonicalJson({
    schema_version: ALERT_SCHEMA, status: 'READY', scoring_time: p.forecast_time,
    inputs_fingerprint: p.inputs_fingerprint, model: Object.keys(model).length ? model : null,
    firms: { origin: p.firms_origin, coverage_end: p.firms_coverage_end,
      lag_days: p.firms_lag_days, status: p.firms_status },
    top_n: topN,
    cells: shown.map(c => [c.rank, c.display_rank, c.tie_group_size, c.cell_id, new PyFloat(c.score)]),
  }));
}
function nonReadyFingerprint(status, reasons) {
  return sha256Hex(canonicalJson({ schema_version: ALERT_SCHEMA, status, reasons: [...reasons].sort() }));
}
// Bridge error types keep alert_payload's non-ready mapping; transport errors are UNAVAILABLE.
const NON_READY = { prototype_unavailable: ['UNAVAILABLE', 'prototype_unavailable'],
  data_unavailable: ['UNAVAILABLE', 'data_unavailable'], internal_error: ['INVALID', 'invalid_result'],
  timeout: ['UNAVAILABLE', 'timeout'], connection_refused: ['UNAVAILABLE', 'connection_refused'],
  transport_error: ['UNAVAILABLE', 'transport_error'] };

function evaluate(envelope, nowIso, executionId) {
  const base = { policy_version: 'sapi-pilot-v1', execution_id: String(executionId),
    evaluated_at: nowIso, delivery: 'NOT_SENT', top_group: [], inputs_fingerprint: null };
  const blocked = (reason, category = 'error') => {
    const [status, why] = NON_READY[reason] || ['INVALID', reason];
    return { ...base, category, reason, alert_identity_verified: false,
      notification_identity: nonReadyFingerprint(status, [why]),
      message: `PRUEBA CONTROLADA — SAPI\nRanking no habilitado: ${reason}.\nNo implica riesgo bajo ni ausencia de incendios.\nEjecución: ${base.execution_id}` };
  };
  if (envelope.error) {
    const label = JSON.stringify(envelope.error);
    const reason = /ETIMEDOUT|ESOCKETTIMEDOUT|timed?\s*out|timeout/i.test(label) ? 'timeout'
      : /ECONNREFUSED|connection refused/i.test(label) ? 'connection_refused' : 'transport_error';
    return blocked(reason);
  }
  let p;
  // n8n HTTP Request 4.x with fullResponse + text format returns the body under `data`.
  const raw = 'data' in envelope ? envelope.data : envelope.body;
  try { p = typeof raw === 'string' ? JSON.parse(raw) : raw; }
  catch { return blocked('invalid_json'); }
  if (envelope.statusCode !== 200) {
    const expected = envelope.statusCode === 503 ? ['prototype_unavailable', 'data_unavailable']
      : envelope.statusCode === 500 ? ['internal_error'] : [];
    return blocked(expected.includes(p?.error_type) ? p.error_type : 'http_error');
  }
  const timestamp = x => typeof x === 'string' && /(?:Z|[+-]\d{2}:\d{2})$/.test(x)
    && Number.isFinite(Date.parse(x));
  if (!p || p.status !== 'ok' || p.model_version !== 'prototype_model_d_v1'
      || p.model_status !== 'PROTOTYPE / EXPLORATORY' || p.station_id !== '330007'
      || p.horizon_hours !== 6 || !timestamp(p.forecast_time) || !timestamp(p.weather_timestamp)
      || !timestamp(nowIso) || !Number.isFinite(p.age_hours)
      || !/^[0-9a-f]{64}$/.test(p.inputs_fingerprint || '')
      || !['current', 'baseline'].includes(p.firms_origin)
      || !/^\d{4}-\d{2}-\d{2}$/.test(p.firms_coverage_end || '')
      || !Number.isInteger(p.firms_lag_days) || typeof p.firms_status !== 'string'
      || !p.meteo_actual || typeof p.meteo_actual.regla_30_30_30 !== 'boolean'
      || !timestamp(p.meteo_actual.momento_observacion)
      || !Array.isArray(p.cells) || p.cells.length !== 50) return blocked('incomplete_or_invalid_payload');
  const cells = p.cells;
  if (new Set(cells.map(c => c.cell_id)).size !== 50
      || new Set(cells.map(c => c.rank)).size !== 50
      || cells.some(c => !/^VP-(?:00[1-9]|0[1-4][0-9]|050)$/.test(c.cell_id)
        || !Number.isFinite(c.score) || c.score < 0 || c.score > 1
        || !Number.isInteger(c.rank) || c.rank < 1 || c.rank > 50
        || !Number.isInteger(c.display_rank) || c.display_rank < 1
        || !Number.isInteger(c.tie_group_size) || c.tie_group_size < 1)) return blocked('invalid_grid');
  const top = cells.filter(c => c.display_rank === 1);
  const maxScore = Math.max(...cells.map(c => c.score));
  if (!top.length || cells.some(c => (c.score === maxScore) !== (c.display_rank === 1))
      || top.some(c => c.tie_group_size !== top.length)) return blocked('incomplete_tie_group');
  // Canonical identity: required, verified, never replaced by a fallback.
  const id = p.alert_identity;
  if (p.output_schema_version !== OUTPUT_SCHEMA || !id || typeof id !== 'object'
      || id.schema_version !== ALERT_SCHEMA || !/^[0-9a-f]{64}$/.test(id.alert_fingerprint || '')
      || !Number.isInteger(id.top_n) || id.top_n < 1 || id.top_n > 50)
    return blocked('missing_alert_identity', 'blocked');
  if (alertFingerprint(p, id.top_n) !== id.alert_fingerprint)
    return blocked('alert_identity_mismatch', 'blocked');
  const identity = { ...base, inputs_fingerprint: p.inputs_fingerprint,
    alert_identity_verified: true, notification_identity: id.alert_fingerprint };
  const withheld = reason => ({ ...identity, category: 'withheld', reason,
    message: `PRUEBA CONTROLADA — SAPI\nRanking no habilitado: ${reason}.\nNo implica riesgo bajo ni ausencia de incendios.\nEjecución: ${base.execution_id}` });
  const now = Date.parse(nowIso), t = Date.parse(p.forecast_time), weather = Date.parse(p.weather_timestamp);
  const end = t + 6 * 3600000;
  if (now < t || now >= end || weather > t || t - weather > 1800000
      || Date.parse(p.meteo_actual.momento_observacion) !== weather
      || p.age_hours < 0 || p.age_hours > 12 || (now - weather) / 3600000 > 12
      || p.freshness !== 'DATOS RECIENTES') return withheld('outside_valid_window');
  const coverage = Date.parse(p.firms_coverage_end + 'T00:00:00Z');
  const lag = (Date.parse(new Date(t).toISOString().slice(0, 10) + 'T00:00:00Z') - coverage) / 86400000;
  if (!Number.isFinite(coverage) || new Date(coverage).toISOString().slice(0, 10) !== p.firms_coverage_end
      || lag !== p.firms_lag_days || lag < 0 || lag > 3 || p.firms_status !== 'FIRMS AL DÍA')
    return withheld('firms_not_current');
  const group = top.map(c => c.cell_id).sort();
  const rule = p.meteo_actual.regla_30_30_30;
  const category = rule ? 'candidate' : 'withheld';
  const reason = rule ? 'relative_top_group_and_meteo_rule' : 'meteo_rule_false';
  return { ...identity, category, reason, top_group: group,
    message: `PRUEBA CONTROLADA — SAPI\nRanking exploratorio; NO probabilidad calibrada; NO confirmación de incendio.\nT: ${p.forecast_time}\nVentana: T < t <= ${new Date(end).toISOString()}\nGrupo superior relativo (display_rank 1): ${group.join(', ')}\nDMC regional: ${p.station_id}; observación: ${p.weather_timestamp}\nRegla 30-30-30: ${rule} (feature y filtro operacional; no evidencia independiente).\nFIRMS: anomalías térmicas satelitales; cobertura ${p.firms_coverage_end}; lag ${lag} días respecto de T.\nEjecución: ${base.execution_id}\nEntradas: ${p.inputs_fingerprint}\nAlerta: ${id.alert_fingerprint}\nSolo preview; no usar para decisiones operacionales.` };
}

// Suppression is POLICY, kept separate from identity: `notification_identity` is never
// changed here. The default reproduces the current safe behaviour; any other choice
// (time window, extra categories, allowing identical retries) is a future human decision
// and must be passed explicitly. An invalid policy never notifies.
const SUPPRESSION_POLICY_VERSION = 'sapi-suppression-v1';
const DEFAULT_SUPPRESSION_POLICY = Object.freeze({
  version: SUPPRESSION_POLICY_VERSION,
  suppress_same_identity: true,       // same identity + category never notifies twice (retries)
  window_minutes: null,               // null = no time-window suppression
  never_notify_categories: Object.freeze(['withheld', 'blocked']),
});
function validSuppressionPolicy(policy) {
  const keys = ['version', 'suppress_same_identity', 'window_minutes', 'never_notify_categories'];
  return !!policy && typeof policy === 'object' && Object.keys(policy).every(k => keys.includes(k))
    && policy.version === SUPPRESSION_POLICY_VERSION && policy.suppress_same_identity === true
    && (policy.window_minutes === null || (Number.isInteger(policy.window_minutes) && policy.window_minutes > 0))
    && Array.isArray(policy.never_notify_categories)
    && ['withheld', 'blocked'].every(c => policy.never_notify_categories.includes(c))
    && policy.never_notify_categories.every(c => ['withheld', 'blocked', 'error', 'candidate'].includes(c));
}

// Retry-safe: the same alert (same identity and category) never notifies twice.
// `blocked` (integrity failure) and `withheld` are never notifiable.
function deduplicate(current, previous, policy = DEFAULT_SUPPRESSION_POLICY) {
  const base = { ...current, suppression_policy: policy && policy.version, delivery: 'NOT_SENT' };
  if (!validSuppressionPolicy(policy)) {
    return { ...base, condition_changed: false, would_notify: false,
      suppressed_by: 'invalid_suppression_policy', recovered_from_error: false };
  }
  const changed = !previous || previous.notification_identity !== current.notification_identity
    || previous.category !== current.category;
  let suppressedBy = null;
  if (policy.never_notify_categories.includes(current.category)) suppressedBy = 'category';
  else if (!changed) suppressedBy = 'same_identity';
  else if (policy.window_minutes !== null && previous && previous.category === current.category
      && Date.parse(current.evaluated_at) - Date.parse(previous.evaluated_at) < policy.window_minutes * 60000)
    suppressedBy = 'time_window';
  return { ...base, condition_changed: changed, would_notify: suppressedBy === null,
    suppressed_by: suppressedBy,
    recovered_from_error: !!previous && previous.category === 'error' && current.category !== 'error' };
}

if (typeof module !== 'undefined') {
  module.exports = { evaluate, deduplicate, alertFingerprint, nonReadyFingerprint,
    canonicalJson, pyFloatRepr, sha256Hex, PyFloat, DEFAULT_SUPPRESSION_POLICY,
    SUPPRESSION_POLICY_VERSION };
}
