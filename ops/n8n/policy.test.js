// Synthetic software fixtures, never Model D evaluation or operational data.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { evaluate, deduplicate } = require('./policy');
const now = '2026-09-24T13:00:00Z';
function payload() {
  return { status: 'ok', model_version: 'prototype_model_d_v1', model_status: 'PROTOTYPE / EXPLORATORY',
    station_id: '330007', horizon_hours: 6, forecast_time: '2026-09-24T12:00:00Z',
    weather_timestamp: '2026-09-24T12:00:00Z', age_hours: 1, freshness: 'DATOS RECIENTES',
    firms_origin: 'current', firms_coverage_end: '2026-09-23', firms_lag_days: 1,
    firms_status: 'FIRMS AL DÍA', inputs_fingerprint: 'a'.repeat(64),
    meteo_actual: {regla_30_30_30: true, momento_observacion: '2026-09-24T12:00:00Z'},
    cells: Array.from({length:50}, (_,i) => ({cell_id:`VP-${String(i+1).padStart(3,'0')}`,
      score: i<2 ? 0.4 : 0.1, rank:i+1, display_rank:i<2 ? 1 : 3, tie_group_size:i<2 ? 2 : 48})) };
}
const run = p => evaluate({statusCode:200,body:p}, now, 'fixture-1');
const matrix = [
  ['A', {statusCode:200,body:payload()}, 'candidate', 'relative_top_group_and_meteo_rule'],
  ['B', {statusCode:503,body:{error_type:'prototype_unavailable'}}, 'error','prototype_unavailable'],
  ['C', {statusCode:503,body:{error_type:'data_unavailable'}}, 'error','data_unavailable'],
  ['D', {statusCode:500,body:{error_type:'internal_error'}}, 'error','internal_error'],
  ['E', {error:{code:'ETIMEDOUT'}}, 'error','timeout'],
  ['F', {error:{code:'ECONNREFUSED'}}, 'error','connection_refused'],
  ['G', {statusCode:200,body:'{broken'}, 'error','invalid_json'],
  ['H', {statusCode:200,body:{status:'ok'}}, 'error','incomplete_or_invalid_payload'],
];
for (const [name,envelope,category,reason] of matrix) test(`matrix ${name}`, () => {
  const r=evaluate(envelope,now,'matrix-'+name);
  assert.equal(r.category,category); assert.equal(r.reason,reason); assert.equal(r.delivery,'NOT_SENT');
  if(name!=='A') assert.deepEqual(r.top_group,[]);
});
test('all ties, scientific message and independent execution identity',()=>{
  const r=run(payload()); assert.deepEqual(r.top_group,['VP-001','VP-002']);
  for(const text of ['PRUEBA CONTROLADA','NO probabilidad calibrada','NO confirmación de incendio',
    'FIRMS','T:', 'Ventana:', 'DMC regional', 'lag 1', 'fixture-1']) assert.ok(r.message.includes(text));
  assert.ok(!r.notification_identity.includes('fixture-1'));
});
test('persistent condition is suppressed despite new inputs or ordering',()=>{
  const a=run(payload()), p=payload();p.inputs_fingerprint='b'.repeat(64);p.cells.reverse();
  const b=deduplicate(run(p),JSON.parse(JSON.stringify(a)));
  assert.equal(b.would_notify,false); assert.equal(b.condition_changed,false);
});
test('group change, repeated error and recovery',()=>{
  const a=run(payload()), p=payload();
  [p.cells[0].cell_id,p.cells[2].cell_id]=[p.cells[2].cell_id,p.cells[0].cell_id];
  assert.equal(deduplicate(run(p),a).would_notify,true);
  const e=evaluate(matrix[1][1],now,'error');
  assert.equal(deduplicate(e,e).would_notify,false);
  assert.equal(deduplicate(a,e).recovered_from_error,true);
  assert.equal(deduplicate(a,e).would_notify,true);
});
for (const [name,change] of [
  ['expired',p=>{p.forecast_time='2026-09-24T06:00:00Z';}],
  ['future weather',p=>{p.weather_timestamp='2026-09-24T13:01:00Z';}],
  ['negative age',p=>{p.age_hours=-1;}],
  ['stale firms',p=>{p.firms_status='FIRMS DESACTUALIZADO';}],
  ['false rule',p=>{p.meteo_actual.regla_30_30_30=false;}],
  ['missing tie',p=>{p.cells[1].display_rank=2;}],
  ['duplicate cell',p=>{p.cells[1].cell_id=p.cells[0].cell_id;}],
  ['missing provenance',p=>{delete p.inputs_fingerprint;}],
]) test(`fail closed: ${name}`,()=>{const p=payload();change(p);assert.notEqual(run(p).category,'candidate');});

// Envelope shape observed in n8n 2.39.10 runtime (fullResponse + responseFormat text).
const n8n = (statusCode, data) => ({statusCode, statusMessage:'x', headers:{}, data});
for (const [name,envelope,category,reason] of [
  ['A', n8n(200, JSON.stringify(payload())), 'candidate', 'relative_top_group_and_meteo_rule'],
  ['B', n8n(503, '{"status":"error","error_type":"prototype_unavailable"}'), 'error','prototype_unavailable'],
  ['C', n8n(503, '{"status":"error","error_type":"data_unavailable"}'), 'error','data_unavailable'],
  ['D', n8n(500, '{"status":"error","error_type":"internal_error"}'), 'error','internal_error'],
  ['E', {error:{message:'timeout of 1000ms exceeded',code:'ECONNABORTED'}}, 'error','timeout'],
  ['G', n8n(200, '{broken'), 'error','invalid_json'],
  ['H', n8n(200, '{"status":"ok"}'), 'error','incomplete_or_invalid_payload'],
]) test(`n8n runtime envelope ${name}`, () => {
  const r=evaluate(envelope,now,'rt-'+name);
  assert.equal(r.category,category); assert.equal(r.reason,reason);
});
