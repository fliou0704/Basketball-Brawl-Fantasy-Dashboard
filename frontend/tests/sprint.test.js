import test from 'node:test';
import assert from 'node:assert/strict';
import {highlightsUrl} from '../src/record-data.js';
import {rankTop150} from '../src/top150-data.js';
import {scoringScale,standingsAllPlay} from '../src/standings-visualization-data.js';
const pool=(players,extra={})=>({completePool:true,maxTeamGames:82,ownershipAvailable:true,players,...extra});
const p=(playerId,fpts,gp=40,fantasyTeam=null)=>({playerId,name:`Player ${playerId}`,fpts,gp,fantasyTeam});
const owner={teamId:1,teamName:'One'};
test('highlight links encode exact saved game date, Unicode and NBA opponent',()=>{
  const url=highlightsUrl({'Player Name':'Luka Dončić',Date:'01/26/2024',nbaOpponent:'Atlanta Hawks','Team Name':'Fantasy Opponent',FPTS:100});
  assert.equal(new URL(url).searchParams.get('search_query'),'Luka Dončić January 26 2024 vs Atlanta Hawks highlights');
  assert.ok(url.includes(encodeURIComponent('Dončić')));assert.equal(new URL(url).searchParams.size,1);
  assert.equal(new URL(highlightsUrl({'Player Name':'A',Date:'invalid'})).searchParams.get('search_query'),'A highlights');
});
test('total ranking keeps true ranks and only rostered players below cutoff',()=>{
  const data=pool([p(1,100,40),p(2,90,40),p(3,80,40),p(4,70,40,owner),p(5,null,null,owner)]);
  const ranking=rankTop150(data,'total',2);
  assert.deepEqual(ranking.top.map(p=>p.playerId),[1,2]);
  assert.deepEqual(ranking.below.map(p=>[p.playerId,p.rank]),[[4,4],[5,null]]);
  assert.equal(ranking.top[0].fantasyTeam,null);
});
test('per-game ranking enforces adjusted GP, updates cutoff and labels NQ',()=>{
  const data=pool([p(1,100,1,owner),p(2,90,30),p(3,80,40,owner),p(4,70,21)]);
  const ranking=rankTop150(data,'perGame',2);
  assert.equal(ranking.minimumGP,21);assert.deepEqual(ranking.top.map(p=>p.playerId),[4,2]);
  assert.deepEqual(ranking.below.map(p=>[p.playerId,p.rank]),[[3,3],[1,null]]);
  for(const [maxTeamGames,minimum] of [[0,1],[20,5],[40,10],[82,21]])assert.equal(rankTop150({...data,maxTeamGames}).minimumGP,minimum);
});
test('ranking ties use secondary metric then numeric ESPN ID',()=>{
  const ranking=rankTop150(pool([p(10,100,20),p(2,100,20),p(1,100,40)]));
  assert.deepEqual(ranking.top.map(p=>p.playerId),[2,10,1]);
});
test('incomplete populations show no rankings and historical ownership has no comparisons',()=>{
  assert.equal(rankTop150({completePool:false,players:[p(1,99)]}).available,false);
  assert.deepEqual(rankTop150(pool([p(1,100),p(2,90,40,owner)],{ownershipAvailable:false}),'total',1).below,[]);
});
test('weekly scoring scale rounds ticks and reserves logo space',()=>{
  const scale=scoringScale([{points:1802},{points:1200}]);
  assert.equal(scale.ticks[0].value,0);assert.equal(scale.ticks.at(-1).value,2000);
  assert.ok(scale.y(1802)>60);assert.equal(scale.y(0),215);
});

test('Home and Standings resolve the same as-of All-Play record without future leakage',()=>{
  const past={weeks:[1],teams:[]},final={weeks:[1,2],teams:[]};
  const history={allPlay:final,allPlayByWeek:{1:past}};
  assert.equal(standingsAllPlay(history,1),past);assert.equal(standingsAllPlay(history,2),final);
  assert.equal(standingsAllPlay({allPlay:final},1),null);
});
