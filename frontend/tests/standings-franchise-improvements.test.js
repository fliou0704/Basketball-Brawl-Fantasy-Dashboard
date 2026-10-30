import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {readFile} from 'node:fs/promises';
import {transformWithOxc} from 'vite';

async function load(file, name, bindings={}) {
  const {code}=await transformWithOxc(await readFile(new URL(`../src/components/${file}.jsx`,import.meta.url),'utf8'),file,{lang:'jsx',jsx:{runtime:'classic'}});
  const body=code.replace(/^import .*;$/gm,'').replace(/export default /g,'').replace(/export /g,'');
  const scope={React,...bindings};
  return new Function(...Object.keys(scope),`${body};return ${name};`)(...Object.values(scope));
}
const wrapper=({children,title})=>React.createElement('div',null,title,children);
test('all-play has separate records and tie-aware percentages',async()=>{
  const AllPlay=await load('AllPlay','AllPlay',{Section:wrapper,TableCard:wrapper,Team:({team})=>React.createElement('span',null,team.teamName)});
  const html=renderToStaticMarkup(React.createElement(AllPlay,{data:{weeks:[1],teams:[{teamId:1,rank:1,teamName:'Old identity',winPct:.75,record:'1–0–1'}]}}));
  for(const text of ['All-Play Standings','1–0–1','75.0%','Old identity','half a win'])assert.ok(html.includes(text));
});
test('verified scoring differences show both values and normal matches stay quiet',async()=>{
  const Difference=await load('ScoreDifference','ScoreDifference');
  assert.equal(renderToStaticMarkup(React.createElement(Difference,{official:100,eligible:100})), '');
  const html=renderToStaticMarkup(React.createElement(Difference,{official:1244,eligible:1242,label:'2023 Week 21'}));
  assert.match(html,/1,244/);assert.match(html,/1,242/);assert.match(html,/historical ESPN scoring records/);
});
test('granular charts retain gaps, reduce labels, expose date hover and season boundaries',async()=>{
  const Trend=await load('FranchiseProfile','Trend',{useState:initial=>[initial==='season'?'week':initial,()=>{}],Card:wrapper,Section:wrapper,TableCard:wrapper});
  const points=Array.from({length:30},(_,i)=>({id:String(i),year:2023+Math.floor(i/20),label:`2023 Week ${i+1}`,tick:`W${i+1}`,x:54+i*20,y:i===5?null:100,value:i,display:String(i),boundary:i===0||i===20}));
  const chart={label:'Weekly Fantasy Points',granular:true,points,ticks:[],viewBox:[0,0,800,260]};
  const html=renderToStaticMarkup(React.createElement(Trend,{data:{label:'Season Fantasy Points'},views:{week:chart}}));
  assert.equal((html.match(/<circle /g)||[]).length,29);
  assert.equal((html.match(/franchise-trend-line/g)||[]).length,27);
  assert.equal((html.match(/season-boundary/g)||[]).length,2);
  assert.match(html,/2023 Week 30/);assert.match(html,/aria-pressed="true"[^>]*>Week/);
  assert.ok((html.match(/text-anchor="middle"/g)||[]).length<15);
});
