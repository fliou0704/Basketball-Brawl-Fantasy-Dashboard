import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const dataUrl=new URL('../public/data/',import.meta.url);
const json=async path=>JSON.parse(await readFile(new URL(path,dataUrl),'utf8'));

test('representative Home, Team, Record Book, and H2H players carry ESPN IDs',async()=>{
  const homepage=await json('homepage.json');
  const season=homepage.calendars.at(-1).season;
  const leaders=await json(`${season}/season-leaders.json`);
  assert.ok(leaders.data[0].playerId);

  const teams=await json('team-stats.json');
  const team=await json(`team-stats/${teams.teams[0].teamId}.json`);
  assert.ok(team.summary.roster[0].playerId);

  const recordBook=await json('record-book.json');
  assert.ok(recordBook.seasons[String(recordBook.defaultYear)].mvp.playerId);

  const h2h=await json('historical-h2h.json');
  const pair=Object.values(h2h.pairs)[0];
  const payload=await json(`historical-h2h/${pair}.json`);
  const firstView=Object.values(payload.historical)[0];
  assert.ok(firstView.history[0].details.players.flat()[0].playerId);
});
