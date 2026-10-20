import test from 'node:test';
import assert from 'node:assert/strict';
import {createHomeClient, selectHomeState, leagueDate} from '../src/home-data.js';

const offseason={phase:'offseason',season:2026,standingsWeek:20,playoffKey:'final'};
const manifest={states:{'2026-10-20':offseason,'2026-10-21':offseason},offseasons:[{after:'2026-04-05',state:offseason}]};
const snapshot={active:true,season:2027,week:1,scoringPeriod:1,asOfDate:'2026-10-20',seasonStart:'2026-10-20',seasonEnd:'2027-04-04',
  state:{phase:'regular',season:2027,week:1,standingsWeek:0,dailyDate:null,weeklyWeek:null},matchups:[],players:[]};

test('2027 week 1 period 1 takes priority over the old offseason, even without performances',()=>{
  const result=selectHomeState(manifest,snapshot,'2026-10-20');
  assert.equal(result.state.season,2027);
  assert.equal(result.current.scoringPeriod,1);
  assert.equal(result.state.phase,'regular');
});

test('date rollover retains last known week with stale warning instead of guessing a new week',()=>{
  const result=selectHomeState(manifest,snapshot,'2026-10-21');
  assert.equal(result.state.week,1);
  assert.equal(result.stale,true);
  const next={...snapshot,week:2,scoringPeriod:8,asOfDate:'2026-10-26',state:{...snapshot.state,week:2}};
  assert.equal(selectHomeState(manifest,next,'2026-10-26').state.week,2);
});

test('stale publication warns and does not turn ongoing matchups into final results',()=>{
  const result=selectHomeState(manifest,snapshot,'2026-10-20',{publishedAt:'2026-10-20T10:00:00Z',now:new Date('2026-10-20T20:00:00Z')});
  assert.equal(result.stale,true);
  assert.equal(result.state.phase,'regular');
});

test('actual offseason and preseason use archive, not an old or future active snapshot',()=>{
  assert.equal(selectHomeState(manifest,snapshot,'2027-04-05').current,null);
  assert.equal(selectHomeState(manifest,snapshot,'2026-10-19').state.phase,'offseason');
  assert.equal(selectHomeState(manifest,{...snapshot,active:false},'2026-10-20').current,null);
});

test('historical previews never leak future snapshot scores',()=>{
  assert.equal(selectHomeState(manifest,snapshot,'2026-10-19',{preview:true}).current,null);
  assert.equal(selectHomeState(manifest,snapshot,'2026-10-21',{preview:true}).current,null);
  assert.equal(selectHomeState(manifest,snapshot,'2026-10-20',{preview:true}).current.season,2027);
});

test('league date uses New York around midnight and ignores the host timezone',()=>{
  assert.equal(leagueDate(new Date('2026-10-21T02:00:00Z')),'2026-10-20');
  assert.equal(leagueDate(new Date('2026-10-21T05:00:00Z')),'2026-10-21');
});

test('new deployment updates scores without re-downloading unchanged payloads on every check',async()=>{
  let version='one'; const calls=[];
  const client=createHomeClient('/',async(url,options)=>{
    calls.push({url,options});
    const path=url.split('?')[0].split('/data/')[1];
    const payload=path==='home-version.json'?{schemaVersion:1,version}
      :path==='homepage.json'?{schemaVersion:1,...manifest}
      :path==='home-current.json'?{schemaVersion:1,...snapshot,matchups:[{scoreDisplay:[version==='one'?'0':'12','0']}]}
      :{schemaVersion:1,data:{0:{teams:[]}}};
    return {ok:true,headers:{get:()=>null},json:async()=>payload};
  });
  const first=await client.load('2026-10-20');
  assert.equal(first.current.matchups[0].scoreDisplay[0],'0');
  const initialDownloads=calls.length;
  await client.load('2026-10-20');
  assert.equal(calls.length,initialDownloads+1);
  assert.equal(calls.at(-1).options.cache,'no-store');
  version='two';
  const second=await client.load('2026-10-20');
  assert.equal(second.current.matchups[0].scoreDisplay[0],'12');
  assert.ok(calls.some(c=>c.url.endsWith('home-current.json?v=two')));
});

test('failed deployment read can retry rather than caching a rejected request',async()=>{
  let fails=true;
  const client=createHomeClient('/',async url=>({ok:!fails || !url.includes('home-current'),
    headers:{get:()=>null},json:async()=>url.includes('home-version')?{schemaVersion:1,version:'v'}
      :url.includes('homepage')?{schemaVersion:1,...manifest}
      :url.includes('home-current')?{schemaVersion:1,...snapshot}:{schemaVersion:1,data:{}}}));
  await assert.rejects(client.load('2026-10-20'));
  fails=false;
  assert.equal((await client.load('2026-10-20')).state.season,2027);
});
