import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {transformWithOxc} from 'vite';

const path='../src/components/FranchiseProfile.jsx';
const source=await readFile(new URL(path,import.meta.url),'utf8');
const {code}=await transformWithOxc(source,path,{lang:'jsx',jsx:{runtime:'classic'}});
const body=code.replace(/^import .*;$/gm,'').replace(/export default /g,'').replace(/export /g,'');
const Section=({title,children})=>React.createElement('section',{},React.createElement('h2',{},title),children);
const Card=({children})=>React.createElement('div',{},children);
const TeamLogo=({team})=>React.createElement('img',{src:team.logo,alt:team.teamName});
function component(tab) {
  const useState=initial=>[initial==='performance'?tab:initial,()=>{}];
  return new Function('React','useState','Card','Section','TableCard','TeamLogo',`${body};return FranchiseProfile;`)(React,useState,Card,Section,Card,TeamLogo);
}
const team={teamId:7,teamName:'Historical name',logo:'logos/old.png',color:'#123456'};
const profile={totals:{seasons:2,completedSeasons:1,championships:1,championshipAppearances:1,playoffAppearances:1,wins:10,losses:5,winPct:2/3,fpts:15000,fpPerStart:null},
  history:[{year:2025,team,owners:['Former owner'],complete:true,record:'10–5',regularFpts:1000,regularRank:2,finalRank:1,champion:true,playoffFinish:'Champion'}],
  trends:{},bestSeason:2025,worstSeason:2025,records:[{label:'Highest-scoring matchup',value:'500 FPTS',year:2025,week:3,team}],achievements:[{year:2025,team,title:'League champion',detail:'10–5 regular season'}]};
const render=tab=>renderToStaticMarkup(React.createElement(component(tab),{profile,records:[{label:'Overall Record',value:'12–5'}],roster:React.createElement('table',{'aria-label':'Existing all-time roster'},React.createElement('tbody')),onSeason:()=>{}}));

test('Summary defaults to Performance with career totals, historic identity and season links',()=>{
  const html=render('performance');
  assert.match(html,/aria-selected="true"[^>]*>Performance/);
  for(const text of ['Franchise Career','All-Time Record','Season-by-Season History','Franchise Trends','Historical name','Former owner','logos/old.png','Unavailable'])assert.ok(html.includes(text),text);
  assert.ok(!html.includes('Existing all-time roster'));
});

test('Summary tabs retain the original roster and expose achievements separately',()=>{
  const roster=render('roster'),achievements=render('achievements');
  assert.ok(roster.includes('Existing all-time roster'));
  assert.ok(!roster.includes('Season-by-Season History'));
  assert.ok(achievements.includes('Highest-scoring matchup'));
  assert.ok(achievements.includes('League champion'));
  assert.ok(!achievements.includes('Existing all-time roster'));
  for(const html of [roster,achievements])assert.ok(html.includes('Franchise Career'));
});
