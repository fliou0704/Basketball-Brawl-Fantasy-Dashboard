import test from 'node:test';
import assert from 'node:assert/strict';
import { defaultTeamTab, selectTeamTab, TEAM_TABS } from '../src/team-tabs.js';

test('Team detail tabs default to Roster and allow each existing section',()=>{
  assert.equal(defaultTeamTab(),'roster');
  assert.deepEqual(TEAM_TABS.map(tab=>tab.label),['Roster','Category Rankings','Weekly Performance','Physicals']);
  for(const tab of TEAM_TABS) assert.equal(selectTeamTab(tab.key),tab.key);
  assert.equal(selectTeamTab('unknown'),'roster');
});
