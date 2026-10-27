import test from 'node:test';
import assert from 'node:assert/strict';
import {matchupKey,matchupLink,scoreboardRoute,loadMatchupWeek,retainSnapshot} from '../src/scoreboard-data.js';
test('matchup route uses season week and sorted team IDs independently of names and ESPN schedule IDs',()=>{
 const match={id:55,teams:[{teamId:9,teamName:'Old'},{teamId:2,teamName:'New'}]};
 assert.equal(matchupKey(match),'2-9');
 const route=matchupLink(2026,17,match);
 assert.deepEqual(scoreboardRoute(route),{season:'2026',week:'17',match:'2-9'});
 match.teams[0].teamName='Renamed';match.id=99;
 assert.equal(matchupLink(2026,17,match),route);
});
test('lazy detail load rejects mixed deployment snapshots and preserves no-cache',async()=>{
 const fetcher=async(url,options)=>{assert.equal(url,'/b/data/matchups/2027/2.json');assert.equal(options.cache,'no-cache');return {ok:true,json:async()=>({schemaVersion:1,updatedAt:'snapshot'})};};
 assert.equal((await loadMatchupWeek('/b/','matchups/2027/2.json','snapshot',fetcher)).schemaVersion,1);
 await assert.rejects(loadMatchupWeek('/b/','matchups/2027/2.json','other',fetcher));
 await assert.rejects(loadMatchupWeek('/','missing',null,async()=>({ok:false})));
});

test('unchanged polling responses retain identity while changed score/version responses advance',()=>{
 const before={data:{updatedAt:'stamp',seasons:[{weeks:[{detailVersion:'v1',matchups:[{actualScores:[10,20]}]}]}]}};
 assert.equal(retainSnapshot(before,structuredClone(before)),before);
 const next=structuredClone(before);next.data.seasons[0].weeks[0].matchups[0].actualScores[0]=11;
 assert.equal(retainSnapshot(before,next),next);
 const corrected=structuredClone(before);corrected.data.seasons[0].weeks[0].detailVersion='v2';
 assert.equal(retainSnapshot(before,corrected),corrected);
 assert.equal(retainSnapshot(null,before),before);
});
