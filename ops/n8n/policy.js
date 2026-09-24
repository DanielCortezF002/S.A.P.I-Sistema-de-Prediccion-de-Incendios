// Conservative pilot policy. Pure functions; no I/O, credentials or delivery.
// This is an operational filter, not a scientific probability threshold.
function evaluate(envelope, nowIso, executionId) {
  const base = { policy_version: 'sapi-pilot-v1', execution_id: String(executionId),
    evaluated_at: nowIso, delivery: 'NOT_SENT', top_group: [], inputs_fingerprint: null };
  const blocked = (reason, category = 'error') => ({ ...base, category, reason,
    notification_identity: JSON.stringify(['sapi-pilot-v1', category, reason]),
    message: `PRUEBA CONTROLADA — SAPI\nRanking no habilitado: ${reason}.\nNo implica riesgo bajo ni ausencia de incendios.\nEjecución: ${base.execution_id}` });
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
  const now = Date.parse(nowIso), t = Date.parse(p.forecast_time), weather = Date.parse(p.weather_timestamp);
  const end = t + 6 * 3600000;
  if (now < t || now >= end || weather > t || t - weather > 1800000
      || Date.parse(p.meteo_actual.momento_observacion) !== weather
      || p.age_hours < 0 || p.age_hours > 12 || (now - weather) / 3600000 > 12
      || p.freshness !== 'DATOS RECIENTES') return blocked('outside_valid_window', 'withheld');
  const coverage = Date.parse(p.firms_coverage_end + 'T00:00:00Z');
  const lag = (Date.parse(new Date(t).toISOString().slice(0, 10) + 'T00:00:00Z') - coverage) / 86400000;
  if (!Number.isFinite(coverage) || new Date(coverage).toISOString().slice(0, 10) !== p.firms_coverage_end
      || lag !== p.firms_lag_days || lag < 0 || lag > 3 || p.firms_status !== 'FIRMS AL DÍA')
    return blocked('firms_not_current', 'withheld');
  const group = top.map(c => c.cell_id).sort();
  const rule = p.meteo_actual.regla_30_30_30;
  const category = rule ? 'candidate' : 'withheld';
  const reason = rule ? 'relative_top_group_and_meteo_rule' : 'meteo_rule_false';
  return { ...base, category, reason, top_group: group, inputs_fingerprint: p.inputs_fingerprint,
    notification_identity: JSON.stringify(['sapi-pilot-v1', category, p.model_version, p.station_id, group, rule]),
    message: `PRUEBA CONTROLADA — SAPI\nRanking exploratorio; NO probabilidad calibrada; NO confirmación de incendio.\nT: ${p.forecast_time}\nVentana: T < t <= ${new Date(end).toISOString()}\nGrupo superior relativo (display_rank 1): ${group.join(', ')}\nDMC regional: ${p.station_id}; observación: ${p.weather_timestamp}\nRegla 30-30-30: ${rule} (feature y filtro operacional; no evidencia independiente).\nFIRMS: anomalías térmicas satelitales; cobertura ${p.firms_coverage_end}; lag ${lag} días respecto de T.\nEjecución: ${base.execution_id}\nEntradas: ${p.inputs_fingerprint}\nSolo preview; no usar para decisiones operacionales.` };
}

function deduplicate(current, previous) {
  const changed = !previous || previous.notification_identity !== current.notification_identity;
  return { ...current, condition_changed: changed,
    would_notify: changed && current.category !== 'withheld',
    recovered_from_error: !!previous && previous.category === 'error' && current.category !== 'error',
    delivery: 'NOT_SENT' };
}

if (typeof module !== 'undefined') module.exports = { evaluate, deduplicate };
