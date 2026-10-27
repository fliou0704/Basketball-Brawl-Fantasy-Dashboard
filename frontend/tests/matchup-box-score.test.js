import test from 'node:test';
import assert from 'node:assert/strict';
import {orientMatchup,comparisonDays,dailyAdvantage,lineupPairs} from '../src/matchup-box-score.js';

test('away stays left even when home wins; all positional data follows team IDs',()=>{
 const match={homeTeamId:1,awayTeamId:2,teams:[{teamId:1},{teamId:2}],actualScores:[300,200],scoreDisplay:['300','200']};
 const detail={homeTeamId:1,awayTeamId:2,days:[{points:[30,20],cumulative:[300,200]}],remaining:[{games:8},{games:4}],completedStarts:[10,6]};
 const view=orientMatchup(match,detail);
 assert.deepEqual(view.match.teams.map(t=>t.teamId),[2,1]);
 assert.deepEqual(view.match.actualScores,[200,300]);
 assert.deepEqual(view.detail.days[0].points,[20,30]);
 assert.deepEqual(view.detail.completedStarts,[6,10]);
 assert.deepEqual(view.detail.remaining.map(r=>r.games),[4,8]);
 assert.deepEqual(detail.remaining.map(r=>r.games),[8,4]);
});
test('future and missing scores have no advantage; ties remain neutral',()=>{
 assert.equal(dailyAdvantage({future:true,points:[0,0]}),null);
 assert.equal(dailyAdvantage({points:[0,null]}),null);
 assert.deepEqual(dailyAdvantage({points:[0,0]}),{winner:null,margin:0});
 assert.deepEqual(dailyAdvantage({points:[40,68.5]}),{winner:1,margin:28.5});
});
test('comparison keeps all verified dates including extended weeks and upcoming days',()=>{
 const calendarDays=Array.from({length:14},(_,i)=>({period:i+1,date:`2026-02-${String(i+9).padStart(2,'0')}`,future:i>1}));
 const result=comparisonDays({calendarDays,days:[{period:1,points:[10,20]}]});
 assert.equal(result.length,14);assert.deepEqual(result[0].points,[10,20]);
 assert.equal(result[13].future,true);assert.equal(result[13].points,undefined);
});
test('daily rows pair actual slots, retain bench separately, and do not infer missing players',()=>{
 const teams=[{teamId:2},{teamId:1}];
 const rows=[{teamId:2,playerId:9,slot:'UT',points:20,eligible:true},{teamId:1,playerId:8,slot:'PG',points:30,eligible:true},{teamId:2,playerId:7,slot:'BE',points:0,gamePoints:100,eligible:false}];
 const pairs=lineupPairs(rows,teams,['PG','UT']);
 assert.equal(pairs[0].label,'PG');assert.equal(pairs[0].players[0],null);assert.equal(pairs[0].players[1].playerId,8);
 assert.equal(pairs[1].players[0].playerId,9);
 const bench=lineupPairs(rows,teams,['PG','UT'],true);
 assert.equal(bench[0].players[0].points,0);assert.equal(bench[0].players[1],null);
});

import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {readFile} from 'node:fs/promises';
import {transformWithOxc} from 'vite';
import {formatCalendarDate,formatCalendarRange} from '../src/fantasy-calendar.js';
async function views(selected='summary') {
 const file=new URL('../src/MatchupDetail.jsx',import.meta.url);
 const source=(await readFile(file,'utf8')).replaceAll('import.meta.env.BASE_URL',JSON.stringify('/'));
 const {code}=await transformWithOxc(source,'MatchupDetail.jsx',{lang:'jsx',jsx:{runtime:'classic'}});
 const body=code.replace(/^import .*;$/gm,'').replace(/export default /g,'').replace(/export /g,'');
 const Box=({children,title})=>React.createElement('div',null,title&&React.createElement('h2',null,title),children);
 const bindings={React,useState:()=>[selected,()=>{}],useEffect:()=>{},Section:Box,Card:Box,TableCard:Box,
  TeamLogo:({team})=>React.createElement('img',{'data-team':team.teamId}),PlayerIdentity:({name})=>React.createElement('span',null,name),PlayerSides:Box,
  formatCalendarDate,formatCalendarRange,formatPublicationTime:()=>'',comparisonDays,dailyAdvantage,lineupPairs};
 return new Function(...Object.keys(bindings),`${body};return {Scorecard,DailyComparison,ScoringBreakdown};`)(...Object.values(bindings));
}
const teams=[{teamId:2,teamName:'Away',color:'#111111'},{teamId:1,teamName:'Home',color:'#222222'}];
test('real comparison markup differentiates future dates from ties and retains official totals',async()=>{
 const {DailyComparison}=await views();
 const markup=renderToStaticMarkup(React.createElement(DailyComparison,{match:{teams,actualScores:[20,48.5]},detail:{reconciled:true,calendarDays:[{period:1,date:'2026-10-26',future:false},{period:2,date:'2026-10-27',future:true}],days:[{period:1,points:[20,48.5]}]}}));
 assert.match(markup,/\+28\.5/);assert.match(markup,/Upcoming/);assert.match(markup,/reconcile to the scoreboard/);
 assert.ok(markup.indexOf('Away')<markup.indexOf('Home'));
 assert.doesNotMatch(markup,/Period [12]/);
});
test('date breakdown labels incomplete lineups and never credits bench fantasy points',async()=>{
 const {ScoringBreakdown}=await views('2026-10-26');
 const detail={lineupSlots:['PG'],calendarDays:[{period:1,date:'2026-10-26'}],days:[{period:1,date:'2026-10-26',lineup:[{teamId:2,playerId:3,name:'Recorded bench',slot:'BE',points:0,gamePoints:99,eligible:false}]}]};
 const markup=renderToStaticMarkup(React.createElement(ScoringBreakdown,{detail,teams}));
 assert.match(markup,/Complete daily lineup unavailable/);assert.match(markup,/99 game FPTS excluded/);assert.match(markup,/0 recorded FPTS/);
 assert.doesNotMatch(markup,/99 recorded FPTS/);
});
