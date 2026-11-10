import test from 'node:test';
import assert from 'node:assert/strict';
import { rankTeamOpacity, selectedRankLabel } from '../src/standings-visualization-data.js';

const teams=[{teamId:1,teamName:'One'},{teamId:2,teamName:'Two'}];

test('rank progression defaults to all teams and can isolate one team',()=>{
  assert.equal(selectedRankLabel(teams,null),'All teams');
  assert.equal(rankTeamOpacity(1,null),1);
  assert.equal(selectedRankLabel(teams,2),'Two');
  assert.equal(rankTeamOpacity(2,2),1);
  assert.equal(rankTeamOpacity(1,2),.16);
  assert.equal(selectedRankLabel(teams,99),'All teams');
});
