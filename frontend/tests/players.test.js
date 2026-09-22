import test from 'node:test';
import assert from 'node:assert/strict';
import { ageOnDate, normalizePlayerSearch, searchPlayers } from '../src/player-data.js';
import { playerRoute } from '../src/site-data.js';

const players=[{playerId:1,name:'Nikola Jokić'},{playerId:1966,name:'LeBron James'}];

test('player routes use ESPN IDs for landing and detail pages',()=>{
  assert.deepEqual(playerRoute('#/players'),{playerId:null});
  assert.deepEqual(playerRoute('#/players/1966'),{playerId:'1966'});
  assert.equal(playerRoute('#/players/lebron-james'),null);
});

test('player search is partial, case-insensitive, and diacritic-normalized',()=>{
  assert.equal(searchPlayers(players,'BRON')[0].playerId,1966);
  assert.equal(searchPlayers(players,'jokic')[0].name,'Nikola Jokić');
  assert.equal(normalizePlayerSearch('Jokić'),'jokic');
});

test('age is calculated around the birthday boundary',()=>{
  assert.equal(ageOnDate('1984-12-30',new Date(2026,11,29)),41);
  assert.equal(ageOnDate('1984-12-30',new Date(2026,11,30)),42);
});
