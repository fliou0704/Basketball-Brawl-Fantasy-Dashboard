import test from 'node:test';
import assert from 'node:assert/strict';
import {validLive,liveConfig,canonicalContext,overlayMatch,overlayHome,overlayDetail,createLiveStore,pollDelay} from '../src/live-data.js';
import {orientMatchup,projectedFinal} from '../src/matchup-box-score.js';
const now=Date.parse('2026-10-31T23:30:00Z'),uuid='11111111-1111-4111-8111-111111111111';
const config=liveConfig({VITE_ENABLE_LIVE_SCORING:'true',VITE_SUPABASE_URL:'https://example.supabase.co',VITE_SUPABASE_PUBLISHABLE_KEY:'sb_publishable_test',VITE_LIVE_LEAGUE_ID:uuid});
const ctx={leagueId:609694684,season:2027,week:2,scoringPeriod:12,date:'2026-10-31',updatedAt:'2026-10-31T20:00:00Z',active:true};
const p=(id,tid,slot,points)=>({playerId:id,teamId:tid,name:String(id),slot,scoringEligible:slot==='PG',fantasyPoints:points,creditedPoints:slot==='PG'?points:0,played:true,injuryStatus:'ACTIVE',gameCoverage:'confirmed',gameIds:[456],stats:{MIN:20}});
const row=()=>({league_id:uuid,season:2027,matchup_period:2,scoring_period:12,scoring_date:ctx.date,schema_version:1,revision:'a'.repeat(64),source_updated_at:'2026-10-31T23:25:00Z',verified_at:'2026-10-31T23:29:00Z',published_at:'2026-10-31T23:25:00Z',snapshot:{schemaVersion:1,leagueId:ctx.leagueId,season:2027,week:2,scoringPeriod:12,date:ctx.date,revision:'a'.repeat(64),updatedAt:'2026-10-31T23:25:00Z',
 teams:[{teamId:1,officialScore:100,officialDailyScore:21,players:[p(10,1,'PG',20),p(11,1,'BE',8),p(12,1,'IR',9)]},{teamId:2,officialScore:200,officialDailyScore:30,players:[p(20,2,'PG',30)]}],matchups:[{teamIds:[1,2],officialScores:[100,200]}],games:[{gameId:456,start:'2026-10-31T23:00:00Z',status:'in-progress'}]}});
const match={status:'current',teams:[{teamId:1},{teamId:2}],actualScores:[80,150],scoreDisplay:['80','150']};
const detail={days:[{period:11,date:'2026-10-30',lineup:[{teamId:1,playerId:99,eligible:true,points:79,gamePoints:79,played:true,slot:'PG',name:'Dropped previously'}],points:[79,170]}],calendarDays:[{period:11,date:'2026-10-30'},{period:12,date:ctx.date}],summaryLineup:[],remaining:[{projection:{remaining:20}},{projection:{remaining:30}}],completedStarts:[1,0],reconciled:true};
const copy=v=>JSON.parse(JSON.stringify(v));

test('disabled default and bad/secret frontend keys cannot activate transport',()=>{
 assert.equal(liveConfig().enabled,false);assert.equal(liveConfig({VITE_ENABLE_LIVE_SCORING:'true',VITE_SUPABASE_PUBLISHABLE_KEY:'sb_secret_wrong'}).valid,false);
});
test('strict context rejects historical, wrong league/season/week/day, stale and newer canonical',()=>{
 assert.ok(validLive(row(),ctx,config,now));
 for(const changed of [{active:false},{leagueId:4},{season:2026},{week:1},{scoringPeriod:11},{date:'2026-10-30'},{updatedAt:'2026-10-31T23:30:00Z'}])assert.equal(validLive(row(),{...ctx,...changed},config,now),false);
 assert.equal(validLive(row(),ctx,config,now+11*60000),false);assert.equal(validLive(null,ctx,config,now),false);
});
test('official discrepancy remains authoritative and source objects remain immutable',()=>{
 const r=row(),before=copy(r),m=overlayMatch(match,r,ctx,config,now);
 assert.deepEqual(m.actualScores,[100,200]);assert.deepEqual(r,before);assert.deepEqual(match.actualScores,[80,150]);
 const d=overlayDetail(detail,match,r,ctx,config,now),day=d.days.find(d=>d.period===12);
 assert.deepEqual(day.points,[21,30]);assert.equal(day.lineup.filter(p=>p.teamId===1).reduce((n,p)=>n+p.points,0),20);
 assert.equal(day.lineup.find(p=>p.playerId===11).gamePoints,8);assert.equal(day.lineup.find(p=>p.playerId===12).points,0);
 assert.equal(d.summaryLineup.find(p=>p.playerId===99).points,79);assert.equal(d.reconciled,false);assert.equal(detail.days.length,1);
});
test('projections preserve canonical baseline and team orientation',()=>{
 const d=overlayDetail(detail,match,row(),ctx,config,now),m=overlayMatch(match,row(),ctx,config,now);
 assert.equal(projectedFinal(m,d,0),100); // 80 baseline + 20, never 100 live + 20.
 const flipped=orientMatchup({...m,homeTeamId:1,awayTeamId:2},d);
 assert.equal(projectedFinal(flipped.match,flipped.detail,0),180);
});
test('dropped current-day contributor prevents unsafe player replacement, not official scores',()=>{
 const d=copy(detail);d.days.push({period:12,date:ctx.date,lineup:[{teamId:1,playerId:999,points:5,eligible:true}]});
 const merged=overlayDetail(d,match,row(),ctx,config,now);assert.equal(merged.liveDetailUnavailable,true);assert.deepEqual(merged.days,d.days);
 assert.deepEqual(overlayMatch(match,row(),ctx,config,now).actualScores,[100,200]);
});
test('Home only overlays matching current scores, not historical best performances',()=>{
 const home={active:true,matchups:[{...match,status:undefined}],players:[{points:79}]};
 assert.equal(overlayHome(home,row(),ctx,config,now).matchups[0].scoreDisplay[0],'100');
 assert.equal(overlayHome(home,row(),{...ctx,active:false},config,now),home);
});
test('malformed roster, game references, and official scores fail closed',()=>{
 for(const mutate of [r=>r.snapshot.teams[0].players[0].gameIds.push(999),r=>r.snapshot.teams[0].players[0].creditedPoints=5,r=>r.snapshot.matchups[0].officialScores[0]=9,r=>r.snapshot.games=null]){
  const r=row();mutate(r);assert.equal(validLive(r,ctx,config,now),false);
 }
});
class Surface extends EventTarget {visibilityState='visible';}
function harness() {
 let time=now,id=0;const tasks=new Map(),requests=[];const doc=new Surface(),win=new Surface();let current=row(),fail=false;
 const timers={setTimeout(fn,ms){const key=++id;tasks.set(key,{fn,at:time+ms});return key;},clearTimeout(key){tasks.delete(key);}};
 const fetcher=async(url,options)=>{requests.push({url,options});if(fail)throw Error('offline');if(String(url).includes('nba-schedule'))return {ok:true,json:async()=>({season:2027,fixtures:[]})};const u=new URL(url);return {ok:true,json:async()=>[u.searchParams.get('select').includes(',snapshot')?copy(current):Object.fromEntries(Object.entries(current).filter(([k])=>k!=='snapshot'))]};};
 const store=createLiveStore(config,{fetcher,clock:()=>time,timers,doc,win,base:'/'});store.setContext(ctx);
 return {store,requests,doc,win,tasks,setRow(v){current=v;},fail(v){fail=v;},async flush(){for(let i=0;i<12;i++)await Promise.resolve();},async advance(ms){time+=ms;for(const [key,t]of [...tasks])if(t.at<=time){tasks.delete(key);t.fn();}await this.flush();}};
}
test('one shared poller, unchanged payload fetched once, metadata every active tick, full cleanup',async()=>{
 const h=harness();h.store.start();h.store.start();await h.flush();assert.equal(h.requests.length,3); // static fixtures, metadata, payload.
 const first=h.store.getSnapshot().row;await h.advance(20000);assert.equal(h.requests.length,4);assert.equal(h.store.getSnapshot().row,first);
 h.doc.visibilityState='hidden';h.doc.dispatchEvent(new Event('visibilitychange'));await h.advance(60000);assert.equal(h.requests.length,4);
 h.store.destroy();assert.equal(h.tasks.size,0);
});
test('out-of-order and failed reads retain last good until freshness expires',async()=>{
 const h=harness();h.store.start();await h.flush();const first=h.store.getSnapshot().row;
 h.setRow({...row(),verified_at:'2026-10-31T23:28:00Z'});await h.advance(20000);assert.equal(h.store.getSnapshot().row,first);assert.equal(h.store.getSnapshot().error,true);
 h.fail(true);await h.advance(11*60000);assert.equal(validLive(h.store.getSnapshot().row,ctx,config,now+12*60000),false);h.store.destroy();
});
test('period rollover clears previous row and historical route stops polling',async()=>{
 const h=harness();h.store.start();await h.flush();h.store.setContext({...ctx,scoringPeriod:13,date:'2026-11-01'});await h.flush();assert.equal(h.store.getSnapshot().row,null);
 h.store.setContext({...ctx,active:false});const count=h.requests.length;await h.advance(300000);assert.equal(h.requests.length,count);h.store.destroy();
});
test('unknown schedule uses five-minute discovery; pregame/live windows use 20 seconds',()=>{
 assert.equal(pollDelay(null,null,now),300000);assert.equal(pollDelay(null,row(),now),20000);
 assert.equal(canonicalContext({season:2027,week:2,scoringPeriod:12,leagueId:ctx.leagueId,asOfDate:ctx.date},ctx.updatedAt).date,ctx.date);
});
test('focus events cannot duplicate an in-flight fetch and destroy aborts it',async()=>{
 let calls=0,signal,resolve;
 const doc=new Surface(),win=new Surface(),timers={setTimeout:()=>1,clearTimeout:()=>{}};
 const store=createLiveStore(config,{clock:()=>now,doc,win,timers,fetcher:async(url,opts)=>{calls++;signal=opts.signal;if(String(url).includes('nba-schedule'))return{ok:true,json:async()=>({season:2027,fixtures:[]})};return new Promise(r=>{resolve=r;});}});
 store.setContext(ctx);store.start();for(let i=0;i<8;i++)await Promise.resolve();
 win.dispatchEvent(new Event('focus'));store.refresh();assert.equal(calls,2);
 store.destroy();assert.equal(signal.aborted,true);resolve({ok:true,json:async()=>[row()]});for(let i=0;i<8;i++)await Promise.resolve();assert.equal(store.getSnapshot().row,null);
});
test('build guard rejects server keys without exposing their values',async()=>{
 const {checkPublicLiveEnv}=await import('../vite.config.js');
 for(const env of [{VITE_SUPABASE_PUBLISHABLE_KEY:'sb_secret_never_bundle'},{VITE_SUPABASE_SECRET_KEY:'private-value'},{VITE_ENABLE_LIVE_SCORING:'true'}])assert.throws(()=>checkPublicLiveEnv(env));
 assert.doesNotThrow(()=>checkPublicLiveEnv({VITE_ENABLE_LIVE_SCORING:'false'}));
});
test('a withdrawn public row clears cached overlay at the next check',async()=>{
 const h=harness();h.store.start();await h.flush();assert.ok(h.store.getSnapshot().row);
 // A scoped empty result represents private/withdrawn data, not a transient network failure.
 const timers={setTimeout:()=>1,clearTimeout:()=>{}};let visible=true;
 const store=createLiveStore(config,{clock:()=>now,timers,doc:new Surface(),win:new Surface(),fetcher:async u=>({ok:true,json:async()=>String(u).includes('nba-schedule')?{season:2027,fixtures:[]}:visible?[row()]:[]})});
 store.setContext(ctx);store.start();for(let i=0;i<15;i++)await Promise.resolve();assert.ok(store.getSnapshot().row);
 visible=false;await store.refresh();assert.equal(store.getSnapshot().row,null);store.destroy();h.store.destroy();
});
test('matching current unavailable scores can be filled; historical unavailable cannot',()=>{
 const missing={...match,status:'unavailable',actualScores:null};
 assert.deepEqual(overlayMatch(missing,row(),ctx,config,now).actualScores,[100,200]);
 assert.equal(overlayMatch(missing,row(),{...ctx,active:false},config,now),missing);
});
