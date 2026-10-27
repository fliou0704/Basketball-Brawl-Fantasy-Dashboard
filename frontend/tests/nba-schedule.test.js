import test from 'node:test';
import assert from 'node:assert/strict';
import {fixturesByTeam,fixturesByDate,playerFutureGames,gameTime} from '../src/nba-schedule.js';
import {loadMatchupWeek} from '../src/scoreboard-data.js';

const fixture={id:1,home:1,away:2,date:'2026-10-27',start:'2026-10-28T01:00:00Z',status:'scheduled',regularSeason:true,timeTBD:false};
test('shared schedule joins by team/date and current player ID; unknown affiliations stay unknown',()=>{
 const data={publishedComplete:true,verifiedAt:'2026-10-27T00:00:00Z',fixtures:[fixture],playerAffiliations:{10:1,20:3,30:0}};
 assert.equal(fixturesByTeam(data,1).length,1);assert.equal(fixturesByDate(data,'2026-10-27').length,1);
 assert.equal(playerFutureGames(data,10,'2026-10-27T16:00:00Z').length,1);
 data.playerAffiliations[10]=3;assert.equal(playerFutureGames(data,10,'2026-10-27T16:00:00Z').length,0);
 assert.equal(playerFutureGames(data,999,'2026-10-27T16:00:00Z'),null);
 assert.deepEqual(playerFutureGames(data,30,'2026-10-27T16:00:00Z'),[]);
 assert.equal(gameTime(fixture),'9:00 PM ET');assert.equal(gameTime({...fixture,timeTBD:true}),'Time TBD');
});
test('midnight UTC is still the previous New York day for dated time-TBD fixtures',()=>{
 const data={publishedComplete:true,verifiedAt:'2026-10-27T00:00:00Z',fixtures:[{...fixture,timeTBD:true,status:'tbd'}],playerAffiliations:{10:1}};
 assert.equal(playerFutureGames(data,10,'2026-10-27T01:00:00Z').length,1);
 assert.equal(playerFutureGames(data,10,'2026-10-28T01:00:00Z').length,0);
});
test('matchup loader joins shared opportunities without copying fixtures into detail payloads',async()=>{
 const timestamp='2026-10-27T16:00:00Z';const paths=[];
 const fetcher=async url=>{paths.push(url);return {ok:true,json:async()=>url.endsWith('week.json')?
   {schemaVersion:1,week:2,updatedAt:timestamp,opportunitiesPath:'matchup-opportunities.json',matchups:[{teamIds:[1],remaining:[{games:null}]}]}:
   url.endsWith('nba-schedule.json')?{schemaVersion:2,updatedAt:timestamp,fixtures:[fixture],teams:[{id:2,abbrev:'TWO'}]}:
   {schemaVersion:1,updatedAt:timestamp,verifiedAt:timestamp,weeks:{2:{1:{games:1,potentialStarts:1,days:[],players:[{playerId:10,proTeamId:1,gameIds:[1]}]}}}}};};
 const value=await loadMatchupWeek('/nba-unit/','week.json',timestamp,fetcher);
 assert.equal(value.matchups[0].remaining[0].players[0].games[0].opponent,'TWO');
 assert.equal(value.matchups[0].remaining[0].potentialStarts,1);assert.equal(paths.length,3);
});
test('a missing or mixed shared schedule preserves actual matchup scores and withholds opportunities',async()=>{
 const timestamp='2026-10-27T16:00:00Z';
 const fetcher=async url=>({ok:!url.endsWith('nba-schedule.json'),json:async()=>url.endsWith('week.json')?
  {schemaVersion:1,week:2,updatedAt:timestamp,opportunitiesPath:'matchup-opportunities.json',matchups:[{teamIds:[1],days:[{points:[12]}],remaining:[{games:12,potentialStarts:9}]}]}:
  {schemaVersion:1,updatedAt:'old'}});
 const value=await loadMatchupWeek('/nba-missing/','week.json',timestamp,fetcher);
 assert.deepEqual(value.matchups[0].days,[{points:[12]}]);assert.equal(value.matchups[0].remaining[0].games,null);
});
test('historical content identity stays independent from a new live schedule clock',async()=>{
 const fetcher=async()=>({ok:true,json:async()=>({schemaVersion:1,updatedAt:null,detailVersion:'history-v1',matchups:[]})});
 const value=await loadMatchupWeek('/history/','week.json','new clock',fetcher,'history-v1');
 assert.equal(value.detailVersion,'history-v1');
 await assert.rejects(loadMatchupWeek('/history/','week.json','new clock',fetcher,'history-v2'));
});
