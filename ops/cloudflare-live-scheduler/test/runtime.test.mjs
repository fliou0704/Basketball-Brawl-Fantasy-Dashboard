import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {Miniflare, createFetchMock, Log, LogLevel} from 'miniflare';

test('real local Workers runtime: cron → SQLite guard → mocked GitHub; persistent replay prevention', async () => {
  const directory=await mkdtemp(join(tmpdir(),'brawl-worker-test-'));
  const root=fileURLToPath(new URL('../src/',import.meta.url));
  const mock=createFetchMock();mock.disableNetConnect();
  const github=mock.get('https://api.github.com');
  const path='/repos/fliou0704/Basketball-Brawl-Fantasy-Dashboard/actions/workflows/live-scoring.yml';
  github.intercept({method:'GET',path}).reply(200,{id:403162553,path:'.github/workflows/live-scoring.yml',state:'active'}).persist();
  github.intercept({method:'GET',path:path+'/runs?branch=main&per_page=20'}).reply(200,{workflow_runs:[]}).persist();
  let posts=0, dispatchedBody;
  github.intercept({method:'POST',path:path+'/dispatches'})
    .reply(options=>{posts++;dispatchedBody=options.body;return {statusCode:200,data:JSON.stringify({workflow_run_id:12345})};}).persist();
  const options={name:'brawl-scheduler-runtime-test',compatibilityDate:'2026-07-30',
    modules:[{type:'ESModule',path:join(root,'worker.mjs')},{type:'ESModule',path:join(root,'scheduler.mjs')}],
    bindings:{SCHEDULER_ENABLED:'true',GITHUB_TOKEN:'github_pat_runtime_fixture_not_a_credential'},
    durableObjects:{DISPATCH_GUARD:{className:'DispatchGuard',useSQLite:true}},
    durableObjectsPersist:directory,fetchMock:mock,log:new Log(LogLevel.NONE)};
  let mf=new Miniflare(options);
  try {
    assert.equal((await mf.dispatchFetch('https://example.com/')).status,404);
    const worker=await mf.getWorker();const scheduledTime=new Date();
    const values=await Promise.all([worker.scheduled({scheduledTime,cron:'*/5 * * * *'}),worker.scheduled({scheduledTime,cron:'*/5 * * * *'})]);
    assert.ok(values.every(v=>v.outcome==='ok'));assert.equal(posts,1);
    const body=await new Response(dispatchedBody).text();
    assert.deepEqual(JSON.parse(body),{ref:'main',inputs:{publish:true,force:false}});
    // Recreate the runtime against the same SQLite directory, simulating eviction/deployment.
    await mf.dispose();mf=new Miniflare(options);
    assert.equal((await (await mf.getWorker()).scheduled({scheduledTime,cron:'*/5 * * * *'})).outcome,'ok');
    assert.equal(posts,1);
    await mf.setOptions({...options,bindings:{...options.bindings,SCHEDULER_ENABLED:'false'}});
    await (await mf.getWorker()).scheduled({scheduledTime:new Date(),cron:'*/5 * * * *'});
    assert.equal(posts,1);
    await mf.setOptions({...options,bindings:{...options.bindings,GITHUB_TOKEN:'invalid'}});
    assert.equal((await (await mf.getWorker()).scheduled({scheduledTime:new Date(),cron:'*/5 * * * *'})).outcome,'exception');
    assert.equal(posts,1);
  } finally { await mf.dispose();await mock.close();await rm(directory,{recursive:true,force:true}); }
});
