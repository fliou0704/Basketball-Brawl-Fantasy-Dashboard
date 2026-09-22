import test from 'node:test';
import assert from 'node:assert/strict';
import { ageOnDate, clearPlayerSearch, defaultPlayerTab, latestPlayerGameSeason, normalizePlayerSearch, playerHref, recentPlayerGames, searchPlayers, selectPlayerTab } from '../src/player-data.js';
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

test('selecting a player clears the reusable search query',()=>{
  assert.equal(clearPlayerSearch('jokic'),'');
});

test('shared player links use ESPN IDs and reject missing IDs',()=>{
  assert.equal(playerHref(1966,'/Basketball-Brawl/'),'/Basketball-Brawl/#/players/1966');
  assert.equal(playerHref(null,'/Basketball-Brawl/'),null);
  assert.equal(playerHref('not-an-id','/Basketball-Brawl/'),null);
});

test('Career is the default player tab and tab choices remain local',()=>{
  assert.equal(defaultPlayerTab(),'career');
  assert.equal(selectPlayerTab('game-log'),'game-log');
  assert.equal(selectPlayerTab('transactions'),'transactions');
  assert.equal(selectPlayerTab('unknown'),'career');
});

test('recent games are newest first, limited to five, and latest season defaults correctly',()=>{
  const games=['2025-10-20','2025-10-25','2025-10-21','2025-10-24','2025-10-22','2025-10-23'].map(date=>({date}));
  assert.deepEqual(recentPlayerGames(games).map(game=>game.date),['2025-10-25','2025-10-24','2025-10-23','2025-10-22','2025-10-21']);
  assert.equal(latestPlayerGameSeason([2023,2026,2025]),2026);
});
