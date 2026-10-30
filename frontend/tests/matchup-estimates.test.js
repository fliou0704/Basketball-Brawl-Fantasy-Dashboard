import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {readFile} from 'node:fs/promises';
import {transformWithOxc} from 'vite';
import {formatCalendarDate} from '../src/fantasy-calendar.js';
import {projectedFinal,projectionDay,projectedPlayers} from '../src/matchup-box-score.js';
async function components(){
 const source=await readFile(new URL('../src/components/MatchupEstimates.jsx',import.meta.url),'utf8');
 const {code}=await transformWithOxc(source,'MatchupEstimates.jsx',{lang:'jsx',jsx:{runtime:'classic'}});
 const body=code.replace(/^import .*;$/gm,'').replace(/export /g,'');
 const bindings={React,PlayerSides:({children})=>React.createElement('div',null,children),PlayerIdentity:({name})=>React.createElement('span',null,name),formatCalendarDate,projectedFinal,projectionDay,projectedPlayers};
 return new Function(...Object.keys(bindings),`${body};return {ProjectionSummary,PotentialPoints,ProjectedLineups};`)(...Object.values(bindings));
}
const teams=[{teamId:2,teamName:'Away'},{teamId:1,teamName:'Home'}];
test('scorecard estimates remain explicitly conditional and completed results have none',async()=>{
 const {ProjectionSummary}=await components();
 const detail={remaining:[{projection:{remaining:25,reason:'Unknown health'}},{projection:{remaining:30}}]};
 const html=renderToStaticMarkup(React.createElement(ProjectionSummary,{detail,match:{status:'current',actualScores:[100,200],teams}}));
 assert.match(html,/125/);assert.match(html,/230/);assert.match(html,/Optimal-lineup estimates/);assert.match(html,/not manager-selected/);
 assert.equal(renderToStaticMarkup(React.createElement(ProjectionSummary,{detail,match:{status:'final',teams}})),'');
});
test('individual forecasts retain projected bench/IR, small samples, and missing means',async()=>{
 const {ProjectedLineups}=await components();const date='2026-11-01';
 const detail={remaining:[{players:[{playerId:1,name:'Starter'},{playerId:2,name:'Projected reserve'}],projection:{days:[{date,points:20,players:[{playerId:1,points:20,sampleSize:10,selected:true,assignedSlot:'PG'},{playerId:2,points:-2,sampleSize:2,selected:false}]}]}},{players:[{playerId:3,name:'Unknown'}],projection:{days:[{date,points:null,players:[{playerId:3,points:null,sampleSize:0,selected:null}]}]}}]};
 const html=renderToStaticMarkup(React.createElement(ProjectedLineups,{detail,teams,date}));
 assert.match(html,/Projected reserve/);assert.match(html,/-2/);assert.match(html,/2 completed NBA games/);assert.match(html,/Limited sample/);assert.match(html,/Selection unavailable/);assert.match(html,/Projected bench/);
});
test('potential points remain unavailable with explicit historical evidence coverage',async()=>{
 const {PotentialPoints}=await components();
 const detail={potential:teams.map(()=>({points:null,leftOnBench:null,efficiency:null,completedDays:2,coveredDays:0,days:[{date:'2026-10-29',points:null}],reason:'Historical roster incomplete'}))};
 const html=renderToStaticMarkup(React.createElement(PotentialPoints,{detail,teams}));assert.match(html,/0\/2 dates/);assert.match(html,/Unavailable/);assert.match(html,/Lineup efficiency/);
});
