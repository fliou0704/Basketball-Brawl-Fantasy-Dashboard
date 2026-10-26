import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {transformWithOxc} from 'vite';
import {formatPublicationTime} from '../src/home-data.js';

// Exercise the actual JSX without adding a browser/test-framework dependency.
async function jsx(path, exports, bindings) {
  const source=await readFile(new URL(path,import.meta.url),'utf8');
  const {code}=await transformWithOxc(source,path,{lang:'jsx',jsx:{runtime:'classic'}});
  const body=code.replace(/^import .*;$/gm,'').replace(/export default /g,'').replace(/export /g,'');
  return new Function(...Object.keys(bindings),`${body}; return {${exports}};`)(...Object.values(bindings));
}
const {PlayerStatLine}=await jsx('../src/components/PlayerStatLine.jsx','PlayerStatLine',{React});
const Section=({title,meta,children})=>React.createElement('section',{},React.createElement('h2',{},title),meta,children);
const Card=({title,children})=>React.createElement('div',{},title,children);
const PlayerIdentity=({name})=>React.createElement('span',{},name);
const Team=({team})=>React.createElement('span',{},team.teamName);
const {Daily,CurrentWeek}=await jsx('../src/components/Recaps.jsx','Daily,CurrentWeek',{React,Section,Card,PlayerIdentity,Team,PlayerStatLine,formatPublicationTime});
const player={playerId:1,name:'Fixture player',team:{teamId:1,teamName:'One'},pointsDisplay:'70',date:'2026-10-23',scoringPeriod:4,
  stats:{PTS:30,REB:10,AST:7,BLK:1,STL:2,TO:3,FGM:10,FGA:20,'3PM':4,'3PA':11}};
const snapshot={season:2027,week:7,players:[player],matchups:[]};

test('publication timestamp uses New York, seconds, and supplied time rather than visitor clock',()=>{
  assert.equal(formatPublicationTime('2026-10-24T04:14:00Z'),'10/24/26 12:14:00 AM');
  assert.equal(formatPublicationTime('2026-12-24T18:14:59Z'),'12/24/26 01:14:59 PM');
  assert.equal(formatPublicationTime(null),null);
  assert.equal(formatPublicationTime('invalid'),null);
});

test('daily and weekly leaderboards render exactly the same breakdown including actual 3PA',()=>{
  const daily=renderToStaticMarkup(React.createElement(Daily,{recap:{date:player.date,leaders:[],players:[player]}}));
  const weekly=renderToStaticMarkup(React.createElement(CurrentWeek,{snapshot}));
  const line=renderToStaticMarkup(React.createElement(PlayerStatLine,{stats:player.stats}));
  assert.ok(daily.includes(line));assert.ok(weekly.includes(line));
  assert.ok(line.includes('<dd>4/11</dd>'));
  assert.ok(renderToStaticMarkup(React.createElement(PlayerStatLine,{stats:{'3PM':4}})).includes('<dd>4/—</dd>'));
});

test('week heading is dynamic and obsolete or unverified live text is absent even when stale',()=>{
  const html=renderToStaticMarkup(React.createElement(CurrentWeek,{snapshot,publishedAt:'2026-10-24T04:14:00Z',stale:true,refreshFailed:true}));
  assert.ok(html.includes('Best Week 7 Performances'));
  assert.ok(html.includes('2027 · Week 7 · Week in Progress'));
  assert.ok(html.includes('Last updated: <time'));
  assert.ok(html.includes('10/24/26 12:14:00 AM'));
  for(const obsolete of ['Older snapshot','Latest available','Scoring Period','Published','may still be in progress','LIVE','Showing the latest'])assert.ok(!html.includes(obsolete),obsolete);
});

test('unknown publication time is omitted rather than fabricated',()=>{
  assert.ok(!renderToStaticMarkup(React.createElement(CurrentWeek,{snapshot})).includes('Last updated:'));
});

test('Daily Recap uses one full-width column and a larger date without changing card styling',async()=>{
  const css=await readFile(new URL('../src/homepage.css',import.meta.url),'utf8');
  assert.match(css,/\.daily-grid \{ grid-template-columns: minmax\(0, 1fr\); \}/);
  assert.match(css,/\.daily-recap > \.section-title > span \{ font-size: \.95rem;/);
  assert.equal([...css.matchAll(/\.daily-grid \{[^}]*grid-template-columns/g)].length,1);
});

test('empty current-week performances hide the entire section and first game reveals it',()=>{
  const empty=renderToStaticMarkup(React.createElement(CurrentWeek,{snapshot:{...snapshot,players:[]}}));
  assert.ok(!empty.includes('Best Week'));
  assert.ok(!empty.includes('No player performances'));
  assert.ok(empty.includes('Current Fantasy Scoreboard'));
  assert.ok(renderToStaticMarkup(React.createElement(CurrentWeek,{snapshot})).includes('Best Week 7 Performances'));
});

test('shared recap renders its own week and preserves lineup',async()=>{
  const {Weekly}=await jsx('../src/components/Recaps.jsx','Weekly',{React,Section,Card,PlayerIdentity,Team,PlayerStatLine,formatPublicationTime});
  const recap={week:12,end:'2026-12-27',leaders:[],closest:[],lineup:[{...player,slot:'PG'}]};
  const html=renderToStaticMarkup(React.createElement(Weekly,{recap}));
  assert.ok(html.includes('Week 12 Recap'));
  assert.ok(html.includes('Fixture player'));
  assert.ok(!html.includes('Weekly Recap'));
});

test('Home regular and playoff branches end with standings and omit removed sections',async()=>{
  const app=await readFile(new URL('../src/App.jsx',import.meta.url),'utf8');
  assert.match(app,/<Standings data=\{standings\} final\/>\s*<\/>:<>/);
  assert.match(app,/<Standings data=\{standings\}\/>\s*<\/>\}/);
  assert.ok(!app.includes('Around'));
  const recaps=await readFile(new URL('../src/components/Recaps.jsx',import.meta.url),'utf8');
  assert.ok(!recaps.includes('Around the League'));
  assert.ok(!recaps.includes('Toughest'));
  assert.ok(recaps.includes('Closest Matchup'));
});
