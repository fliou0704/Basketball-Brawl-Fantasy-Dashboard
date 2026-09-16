import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { latestTeamSeason, selectSeasonView, teamIdFromRoute } from '../src/site-data.js';

const dataUrl=new URL('../public/data/',import.meta.url);
const json=async path=>JSON.parse(await readFile(new URL(path,dataUrl),'utf8'));

test('stable team routes resolve IDs and reject landing routes',()=>{
  assert.equal(teamIdFromRoute('#/teams/16'),'16');
  assert.equal(teamIdFromRoute('#teams/2'),'2');
  assert.equal(teamIdFromRoute('#/teams'),null);
  assert.equal(teamIdFromRoute('#/teams/name'),null);
});

test('team pages default to the latest season available to that franchise',async()=>{
  const manifest=await json('team-stats.json');
  for(const team of manifest.teams){
    const payload=await json(`team-stats/${team.teamId}.json`);
    const available=manifest.years.find(year=>payload.seasons[year]);
    assert.equal(latestTeamSeason(payload),String(available));
    assert.equal(payload.team.teamName,team.teamName);
  }
});

test('historical seasons retain snapshots matching exported standings',async()=>{
  const manifest=await json('team-stats.json');
  for(const year of manifest.years){
    const final=manifest.standings[year];
    for(const row of final.teams){
      const team=await json(`team-stats/${row.teamId}.json`);
      const snapshot=team.seasons[year].snapshot;
      assert.deepEqual([snapshot.rank,snapshot.record,snapshot.pointsFor,snapshot.pointsAgainst],[row.rank,row.record,row.pointsFor,row.pointsAgainst]);
    }
  }
});

test('completed seasons show final brackets and pre-playoff seasons do not',()=>{
  const complete={calendars:[{season:2025,complete:true}],states:{}};
  assert.equal(selectSeasonView(complete,2025,{20:{season:2025}},{final:{rounds:[1]}},'2025-01-01').bracket.rounds.length,1);
  const current={calendars:[{season:2026,complete:false}],states:{'2026-01-01':{season:2026,phase:'regular',playoffKey:null}}};
  assert.equal(selectSeasonView(current,2026,{3:{season:2026}},{21:{rounds:[1]}},'2026-01-01').bracket,null);
  current.states['2026-03-01']={season:2026,phase:'playoffs',playoffKey:'21'};
  assert.equal(selectSeasonView(current,2026,{20:{season:2026}},{21:{rounds:[1]}},'2026-03-01').bracket.rounds.length,1);
});
