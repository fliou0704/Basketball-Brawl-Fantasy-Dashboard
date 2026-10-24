import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {adjacentWeek, loadScoreboard, scoreboardLink, scoreboardRoute, selectScoreboard} from '../src/scoreboard-data.js';
const data={current:{season:2027,week:1},seasons:[{season:2026,weeks:[{week:1},{week:23}]},{season:2027,weeks:[{week:1},{week:2},{week:20}]}]};
test('default and first-day selection use ESPN snapshot rather than completed weeks',()=>{
  assert.equal(selectScoreboard(data).season.season,2027);
  assert.equal(selectScoreboard(data).selected.week,1);
});
test('deep links retain historical and future weeks on refresh and back/forward',()=>{
  for(const requested of [{season:2026,week:23},{season:2027,week:2},{season:2027,week:1}]) {
    const route=scoreboardLink(requested.season,requested.week);
    const selection=selectScoreboard(data,scoreboardRoute(route));
    assert.equal(selection.season.season,requested.season);
    assert.equal(selection.selected.week,requested.week);
  }
  assert.equal(selectScoreboard(data,{season:1999}),null);
  assert.equal(selectScoreboard(data,{season:2027,week:999}),null);
  assert.equal(scoreboardRoute('#/players'),null);
});
test('arrows cross season boundaries and stop at known endpoints',()=>{
  assert.deepEqual(adjacentWeek(data,2027,1,-1),{season:2026,week:23});
  assert.deepEqual(adjacentWeek(data,2026,23,1),{season:2027,week:1});
  assert.equal(adjacentWeek(data,2026,1,-1),null);
  assert.equal(adjacentWeek(data,2027,20,1),null);
  assert.equal(selectScoreboard(data,{season:2026}).selected.week,23);
});
test('client bypasses stale cache and preserves publication metadata',async()=>{
  const loaded=await loadScoreboard('/brawl/',async(url,options)=>{
    assert.equal(url,'/brawl/data/scoreboard.json');assert.equal(options.cache,'no-cache');
    return {ok:true,json:async()=>({schemaVersion:1,...data}),headers:new Map([['last-modified','Sat, 24 Oct 2026 12:00:00 GMT']])};
  });
  assert.equal(loaded.data.current.week,1);assert.ok(loaded.publishedAt);
  await assert.rejects(loadScoreboard('/',async()=>({ok:false})));
});
test('routing updates selection through the existing hashchange listener',async()=>{
  const main=await readFile(new URL('../src/main.jsx',import.meta.url),'utf8');
  assert.match(main,/addEventListener\('hashchange',update\)/);
  assert.match(main,/<ScoreboardPage requested=\{scoreboard\}/);
});
