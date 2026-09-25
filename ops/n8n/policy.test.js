// Synthetic software fixtures, never Model D evaluation or operational data.
// fixtures/*.json are real bridge output for a synthetic GridScoreResult, generated and
// kept current by tests/test_output_pipeline.py: their alert_fingerprint comes from Python.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { evaluate, deduplicate, alertFingerprint } = require('./policy');
const CANONICAL = require('./fixtures/canonical-notification.json');
const TAMPERED = require('./fixtures/tampered-identity.json');
const now = '2026-09-24T13:00:00Z';
const payload = () => JSON.parse(JSON.stringify(CANONICAL));
// Re-sign a deliberately modified payload with the canonical recipe (to test policy rules
// other than identity integrity).
const resign = p => { p.alert_identity.alert_fingerprint = alertFingerprint(p, p.alert_identity.top_n); return p; };
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
test('canonical fixture: identity from Python is verified and used as-is',()=>{
  const r=run(payload());
  assert.equal(r.alert_identity_verified,true);
  assert.equal(r.notification_identity,CANONICAL.alert_identity.alert_fingerprint);
  assert.equal(r.inputs_fingerprint,CANONICAL.inputs_fingerprint);
});
test('tampered fixture is blocked and never notifiable',()=>{
  const r=run(JSON.parse(JSON.stringify(TAMPERED)));
  assert.equal(r.category,'blocked'); assert.equal(r.reason,'alert_identity_mismatch');
  assert.equal(r.alert_identity_verified,false);
  assert.equal(deduplicate(r,null).would_notify,false);
});
for (const [name,change,reason] of [
  ['missing identity',p=>{delete p.alert_identity;},'missing_alert_identity'],
  ['missing output schema',p=>{delete p.output_schema_version;},'missing_alert_identity'],
  ['malformed fingerprint',p=>{p.alert_identity.alert_fingerprint='x';},'missing_alert_identity'],
  ['foreign identity',p=>{p.alert_identity.alert_fingerprint='0'.repeat(64);},'alert_identity_mismatch'],
  ['changed inputs',p=>{p.inputs_fingerprint='b'.repeat(64);},'alert_identity_mismatch'],
  ['changed top score',p=>{p.cells[0].score=p.cells[1].score=0.39;},'alert_identity_mismatch'],
]) test(`identity fail closed: ${name}`,()=>{
  const p=payload(); change(p); const r=run(p);
  assert.equal(r.category,'blocked'); assert.equal(r.reason,reason);
  assert.equal(deduplicate(r,null).would_notify,false);
});
test('all ties, scientific message and independent execution identity',()=>{
  const r=run(payload()); assert.deepEqual(r.top_group,['VP-001','VP-002']);
  for(const text of ['PRUEBA CONTROLADA','NO probabilidad calibrada','NO confirmación de incendio',
    'FIRMS','T:', 'Ventana:', 'DMC regional', 'lag 1', 'fixture-1', 'Alerta:']) assert.ok(r.message.includes(text));
  assert.ok(!r.notification_identity.includes('fixture-1'));
});
test('retry of the same alert is suppressed, also with cells reordered',()=>{
  const a=run(payload()), p=payload(); p.cells.reverse();
  const b=deduplicate(run(p),JSON.parse(JSON.stringify(a)));
  assert.equal(b.notification_identity,a.notification_identity);
  assert.equal(b.would_notify,false); assert.equal(b.condition_changed,false);
});
test('a new evaluation (new inputs) is a new alert even with the same top group',()=>{
  const a=run(payload()), p=resign(Object.assign(payload(),{inputs_fingerprint:'b'.repeat(64)}));
  const b=deduplicate(run(p),a);
  assert.deepEqual(b.top_group,a.top_group); assert.notEqual(b.notification_identity,a.notification_identity);
  assert.equal(b.would_notify,true);
});
test('group change, repeated error and recovery',()=>{
  const a=run(payload()), p=payload();
  [p.cells[0].cell_id,p.cells[2].cell_id]=[p.cells[2].cell_id,p.cells[0].cell_id];
  assert.equal(deduplicate(run(resign(p)),a).would_notify,true);
  const e=evaluate(matrix[1][1],now,'error');
  assert.equal(deduplicate(e,e).would_notify,false);
  assert.equal(deduplicate(a,e).recovered_from_error,true);
  assert.equal(deduplicate(a,e).would_notify,true);
});
test('same alert moving from withheld to candidate is notified once',()=>{
  const early=evaluate({statusCode:200,body:payload()},'2026-09-24T11:00:00Z','early');
  assert.equal(early.category,'withheld');
  const later=deduplicate(run(payload()),early);
  assert.equal(later.would_notify,true);
  assert.equal(deduplicate(run(payload()),later).would_notify,false);
});
for (const [name,change] of [
  ['expired',p=>{p.forecast_time='2026-09-24T06:00:00+00:00';}],
  ['future weather',p=>{p.weather_timestamp='2026-09-24T13:01:00+00:00';}],
  ['negative age',p=>{p.age_hours=-1;}],
  ['stale firms',p=>{p.firms_status='FIRMS DESACTUALIZADO';}],
  ['false rule',p=>{p.meteo_actual.regla_30_30_30=false;}],
  ['missing tie',p=>{p.cells[1].display_rank=2;}],
  ['duplicate cell',p=>{p.cells[1].cell_id=p.cells[0].cell_id;}],
  ['missing provenance',p=>{delete p.inputs_fingerprint;}],
]) test(`fail closed: ${name}`,()=>{
  const p=payload(); change(p); if (p.inputs_fingerprint) resign(p);
  assert.notEqual(run(p).category,'candidate');
});

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
