import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {runTick, REPO, WORKFLOW} from '../src/scheduler.mjs';

const TOKEN = 'github_pat_fixture_not_a_credential';
function context(map = new Map()) {
  let tail = Promise.resolve();
  return {map, storage: {async get(k) { return structuredClone(map.get(k)); }, async put(k,v) { map.set(k, structuredClone(v)); }},
    blockConcurrencyWhile(fn) { const p = tail.then(fn); tail = p.catch(() => {}); return p; }};
}
function harness() {
  let time = Math.floor(Date.now()/300_000)*300_000, runs = [], workflowState = 'active', postStatus = 204, custom;
  const calls = [], ctx = context(), env = {SCHEDULER_ENABLED: 'true', GITHUB_TOKEN: TOKEN};
  const io = {now: () => time, sleep: async () => {}, fetch: async (url, options) => {
    calls.push({url, ...options});
    if (custom) { const response = await custom(url, options); if (response) return response; }
    if (options.method === 'POST') return postStatus === 204 ? new Response(null,{status:204}) : Response.json({workflow_run_id:12345},{status:postStatus});
    if (url.includes('/runs?')) return Response.json({workflow_runs:runs});
    return Response.json({id:403162553,path:'.github/workflows/live-scoring.yml',state:workflowState});
  }};
  return {ctx, env, io, calls, get time() { return time; }, advance(ms) { time += ms; },
    runs(v) { runs=v; }, state(v) { workflowState=v; }, postStatus(v) { postStatus=v; }, fetch(v) { custom=v; },
    tick(t=time,c=ctx) { return runTick(c,env,t,io); }};
}
const run = (h, changes={}) => ({id:9,workflow_id:403162553,head_branch:'main',status:'completed',created_at:new Date(h.time-300_000).toISOString(),...changes});

test('disabled/default/invalid credentials cause no GitHub requests', async () => {
  for (const change of [{SCHEDULER_ENABLED:'false'},{SCHEDULER_ENABLED:undefined},{GITHUB_TOKEN:undefined},{GITHUB_TOKEN:'ghp_classic_rejected'}]) {
    const h=harness();Object.assign(h.env,change);await h.tick();assert.equal(h.calls.length,0);
  }
});
test('fixed destination, exact approved dispatch inputs, timeout and redirect protection', async () => {
  const h=harness();const result=await h.tick();assert.equal(result.status,'accepted');
  assert.equal(h.calls.length,3);
  const p=h.calls.at(-1);assert.equal(p.url,`https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`);
  assert.deepEqual(JSON.parse(p.body),{ref:'main',inputs:{publish:true,force:false}});
  assert.equal(p.redirect,'manual');assert.ok(p.signal instanceof AbortSignal);
  assert.equal(p.headers.Authorization,`Bearer ${TOKEN}`);
});
test('new 200 response exposes only a constructed safe run URL; 204 is also accepted', async () => {
  const h=harness();h.postStatus(200);const r=await h.tick();assert.equal(r.runId,12345);
  assert.equal(r.runUrl,`https://github.com/${REPO}/actions/runs/12345`);
});
test('duplicate concurrent ticks and cold object recreation preserve one persistent claim', async () => {
  const h=harness();const values=await Promise.all([h.tick(),h.tick(),h.tick()]);
  assert.equal(values.filter(v=>v.status==='accepted').length,1);
  const fresh=context(h.ctx.map);assert.equal((await h.tick(h.time,fresh)).code,'duplicate_or_old_tick');
  assert.equal(h.calls.filter(v=>v.method==='POST').length,1);
});
test('new five-minute period can dispatch; old/reordered ticks cannot', async () => {
  const h=harness();const first=h.time;await h.tick();h.advance(300_000);
  assert.equal((await h.tick()).status,'accepted');assert.equal((await h.tick(first)).status,'skipped');
});
test('stale/future/invalid ticks cause no network', async () => {
  const h=harness();for(const t of [h.time-240_001,h.time+60_001,NaN,'now']) assert.equal((await h.tick(t)).code,'stale_or_invalid_tick');
  assert.equal(h.calls.length,0);
});
test('persisted in-flight lease blocks a different tick', async () => {
  const h=harness();h.ctx.map.set('guard',{version:1,lastSlot:Math.floor(h.time/300_000)-1,leaseUntil:h.time+30_000,lastPostAt:0});
  assert.equal((await h.tick()).code,'dispatch_in_flight');assert.equal(h.calls.length,0);
});
test('cross-boundary cooldown cannot be bypassed by repeated event delivery', async () => {
  const h=harness();await h.tick(h.time-200_000);h.advance(100_000);
  assert.equal((await h.tick()).code,'dispatch_cooldown');
  assert.equal((await h.tick()).code,'duplicate_or_old_tick');
});
test('all non-completed statuses, including waiting and unknown, block overlap', async () => {
  for(const status of ['queued','in_progress','waiting','pending','requested','unknown']) {
    const h=harness();h.runs([run(h,{status})]);assert.equal((await h.tick()).code,'workflow_busy');
    assert.equal(h.calls.filter(c=>c.method==='POST').length,0);
  }
});
test('recent native/manual run prevents duplicate dispatch; older completed run permits it', async () => {
  const h=harness();h.runs([run(h,{created_at:new Date(h.time-1000).toISOString()})]);assert.equal((await h.tick()).code,'recent_run');
  h.advance(300_000);assert.equal((await h.tick()).status,'accepted');
});
test('workflow disabled is an independent server-side stop', async () => {
  const h=harness();h.state('disabled_manually');assert.equal((await h.tick()).code,'workflow_disabled');assert.equal(h.calls.length,1);
});
test('wrong workflow identity, run identity, timestamp and malformed data fail closed', async () => {
  for(const mutate of [h=>h.runs([run(h,{workflow_id:4})]),h=>h.runs([run(h,{head_branch:'codex'})]),h=>h.runs([run(h,{created_at:'bad'})]),h=>h.runs([run(h,{created_at:new Date(h.time+120_000).toISOString()})]),
    h=>h.fetch(async()=>Response.json({wrong:true})),h=>h.fetch(async()=>new Response('not JSON'))]) {
    const h=harness();mutate(h);assert.equal((await h.tick()).status,'error');assert.equal(h.calls.filter(c=>c.method==='POST').length,0);
  }
});
test('bounded GET retry recovers a transient failure but never loops indefinitely', async () => {
  const h=harness();let attempts=0;h.fetch(async()=>{if(++attempts===1)return new Response(null,{status:503});});
  assert.equal((await h.tick()).status,'accepted');assert.equal(h.calls.length,4);
  const bad=harness();bad.fetch(async()=>new Response(null,{status:503}));assert.equal((await bad.tick()).status,'error');assert.equal(bad.calls.length,2);
});
test('long Retry-After defers; auth errors do not retry; messages/bodies never leak', async () => {
  for(const status of [401,403,429]) {
    const h=harness();h.fetch(async()=>new Response(TOKEN,{status,headers:{'retry-after':'120'}}));
    const result=await h.tick();assert.equal(result.status,'error');assert.equal(h.calls.length,1);assert.ok(!JSON.stringify(result).includes(TOKEN));
  }
});
test('ambiguous dispatch (network, 5xx, timeout) is not replayed, including redelivery', async () => {
  for(const mode of ['network','5xx','timeout']) {
    const h=harness();h.fetch(async(_,opts)=>{if(opts.method==='POST'){
      if(mode==='5xx')return new Response(TOKEN,{status:503});
      throw Object.assign(new Error(TOKEN),{name:mode==='timeout'?'AbortError':'Error'});
    }});
    const result=await h.tick();assert.equal(result.code,'dispatch_ambiguous');assert.ok(!JSON.stringify(result).includes(TOKEN));
    await h.tick();assert.equal(h.calls.filter(c=>c.method==='POST').length,1);
  }
});
test('storage failure blocks dispatch without exposing its exception', async () => {
  const h=harness();h.ctx.storage.get=async()=>{throw Error(TOKEN);};const result=await h.tick();
  assert.equal(result.status,'error');assert.equal(h.calls.length,0);assert.ok(!JSON.stringify(result).includes(TOKEN));
});
test('expired total deadline and corrupt persisted state cannot authorize a dispatch', async () => {
  const h=harness();h.fetch(async()=>{h.advance(46_000);});
  assert.equal((await h.tick()).code,'deadline_exceeded');assert.equal(h.calls.filter(c=>c.method==='POST').length,0);
  const corrupt=harness();corrupt.ctx.map.set('guard',{version:2});
  assert.equal((await corrupt.tick()).code,'invalid_guard_state');assert.equal(corrupt.calls.length,0);
});
test('redirect response is rejected without forwarding credentials', async () => {
  const h=harness();h.fetch(async()=>new Response(null,{status:302,headers:{location:'https://example.com/'}}));
  assert.equal((await h.tick()).code,'github_http_error');assert.equal(h.calls.length,1);
});
test('deploy config stays free-plan SQLite, disabled, five-minute and without public routes', () => {
  const config=JSON.parse(fs.readFileSync(new URL('../wrangler.jsonc',import.meta.url),'utf8'));
  assert.equal(config.vars.SCHEDULER_ENABLED,'false');assert.equal(config.workers_dev,false);assert.equal(config.preview_urls,false);
  assert.deepEqual(config.triggers.crons,['*/5 * * * *']);assert.deepEqual(config.migrations[0].new_sqlite_classes,['DispatchGuard']);
  assert.equal(config.routes,undefined);assert.equal(config.vars.GITHUB_TOKEN,undefined);
});
