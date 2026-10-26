import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {transformWithOxc} from 'vite';
import {formatPublicationTime,showHomeRecap} from '../src/home-data.js';

// Exercise the actual JSX without adding a browser/test-framework dependency.
async function jsx(path, exports, bindings) {
  const source=(await readFile(new URL(path,import.meta.url),'utf8')).replaceAll('import.meta.env.BASE_URL',JSON.stringify('/'));
  const {code}=await transformWithOxc(source,path,{lang:'jsx',jsx:{runtime:'classic'}});
  const body=code.replace(/^import .*;$/gm,'').replace(/export default /g,'').replace(/export /g,'');
  return new Function(...Object.keys(bindings),`${body}; return {${exports}};`)(...Object.values(bindings));
}
const {PlayerStatLine}=await jsx('../src/components/PlayerStatLine.jsx','PlayerStatLine',{React});
const Section=({title,meta,children})=>React.createElement('section',{},React.createElement('h2',{},title),meta,children);
const Card=({title,children})=>React.createElement('div',{},title,children);
const PlayerIdentity=({name})=>React.createElement('span',{},name);
const Team=({team})=>React.createElement('span',{},team.teamName);
const {Daily,Weekly,WeeklyPlayerStats,CurrentWeek,CurrentWeekPerformances}=await jsx('../src/components/Recaps.jsx','Daily,Weekly,WeeklyPlayerStats,CurrentWeek,CurrentWeekPerformances',{React,Section,Card,PlayerIdentity,Team,PlayerStatLine,formatPublicationTime});
const {HomeSections}=await jsx('../src/components/HomeSections.jsx','HomeSections',{React,Daily,Weekly,CurrentWeek,CurrentWeekPerformances,
  Standings:()=>React.createElement('h2',{},'Standings'),Playoffs:()=>React.createElement('h2',{},'Playoffs')});
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
  assert.ok(html.includes('2027 Week 7 Scoreboard'));
  assert.ok(html.includes('Last updated: <time'));
  assert.ok(html.includes('10/24/26 12:14:00 AM'));
  for(const obsolete of ['Current Fantasy Scoreboard','Week in Progress','Older snapshot','Latest available','Scoring Period','Published','may still be in progress','LIVE','Showing the latest'])assert.ok(!html.includes(obsolete),obsolete);
  assert.ok(renderToStaticMarkup(React.createElement(CurrentWeek,{snapshot:{...snapshot,season:2028,week:12}})).includes('2028 Week 12 Scoreboard'));
});

test('unknown publication time is omitted rather than fabricated',()=>{
  assert.ok(!renderToStaticMarkup(React.createElement(CurrentWeek,{snapshot})).includes('Last updated:'));
});

test('daily title uses its actual New York recap date with no redundant badge',async()=>{
  const html=renderToStaticMarkup(React.createElement(Daily,{recap:{date:'2026-10-25',leaders:[],players:[player]}}));
  assert.ok(html.includes('<h2>October 25, 2026 Recap</h2>'));
  assert.ok(!html.includes('Oct 25'));
  assert.ok(!html.includes('Daily Recap'));
  const winter=renderToStaticMarkup(React.createElement(Daily,{recap:{date:'2027-01-01',leaders:[],players:[player]}}));
  assert.ok(winter.includes('January 1, 2027 Recap'));
  assert.equal(renderToStaticMarkup(React.createElement(Daily,{recap:{players:[]}})),'');
  const css=await readFile(new URL('../src/homepage.css',import.meta.url),'utf8');
  assert.match(css,/\.daily-grid \{ grid-template-columns: minmax\(0, 1fr\); \}/);
  assert.equal([...css.matchAll(/\.daily-grid \{[^}]*grid-template-columns/g)].length,1);
});

test('empty current-week performances hide the entire section and first game reveals it',()=>{
  const empty=renderToStaticMarkup(React.createElement(CurrentWeek,{snapshot:{...snapshot,players:[]}}));
  assert.ok(!empty.includes('Best Week'));
  assert.ok(!empty.includes('No player performances'));
  assert.ok(empty.includes('2027 Week 7 Scoreboard'));
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

test('Home orders real sections by canonical score coverage without duplicates or empty cards',()=>{
  const state={phase:'regular',week:2,weeklyWeek:1,scoringPeriod:7,weekScoringPeriods:[7,8,9]};
  const daily={date:'2026-10-25',leaders:[],players:[player]};
  const recap={week:1,end:'2026-10-25',leaders:[],closest:[],lineup:[]};
  const titles=(status,{eligible=true,players=[player],phase='regular'}={})=>{
    const selected={...state,phase,scoringPeriod:eligible?7:9};
    const html=renderToStaticMarkup(React.createElement(HomeSections,{
      snapshot:{...snapshot,week:2,scoringStatus:status,players,state:selected},daily,
      weekly:showHomeRecap(selected)?recap:null}));
    return [...html.matchAll(/<h2>(.*?)<\/h2>/g)].map(match=>match[1]);
  };
  assert.deepEqual(titles('zero'),['Week 1 Recap','October 25, 2026 Recap','2027 Week 2 Scoreboard','Standings']);
  assert.deepEqual(titles('started'),['2027 Week 2 Scoreboard','Best Week 2 Performances','October 25, 2026 Recap','Week 1 Recap','Standings']);
  assert.deepEqual(titles('started',{eligible:false}),['2027 Week 2 Scoreboard','Best Week 2 Performances','October 25, 2026 Recap','Standings']);
  assert.deepEqual(titles('zero',{eligible:false,players:[]}),['October 25, 2026 Recap','2027 Week 2 Scoreboard','Standings']);
  assert.deepEqual(titles('unavailable',{players:[]}),['2027 Week 2 Scoreboard','October 25, 2026 Recap','Week 1 Recap','Standings']);
  assert.deepEqual(titles('started',{phase:'playoffs'}).slice(-2),['Playoffs','Standings']);
});

test('weekly stats render GP, one-decimal averages, cumulative shooting and safe unknowns',()=>{
  const stats={gamesPlayed:2,perGame:{PTS:20,REB:5,AST:4,BLK:1,STL:2,TO:3},
    totals:{FGM:4,FGA:20,'3PM':2,'3PA':10},shooting:{'FG%':20,'3P%':20}};
  const html=renderToStaticMarkup(React.createElement(WeeklyPlayerStats,{stats}));
  assert.ok(html.includes('<dt>GP</dt><dd>2</dd>'));
  assert.ok(html.includes('<dt>PTS/G</dt><dd>20.0</dd>'));
  assert.ok(html.includes('4/20 (20.0%)'));
  assert.ok(html.includes('2/10 (20.0%)'));
  const empty=renderToStaticMarkup(React.createElement(WeeklyPlayerStats,{}));
  assert.ok(empty.includes('—/— (—)'));
  assert.ok(!/NaN|Infinity/.test(empty));
});

test('weekly recap cards and players stay single-column at every breakpoint',async()=>{
  const css=await readFile(new URL('../src/homepage.css',import.meta.url),'utf8');
  assert.match(css,/\.weekly-recap \.recap-highlights, \.weekly-recap \.lineup \{ grid-template-columns: minmax\(0, 1fr\); \}/);
  assert.ok(!/\.lineup \{[^}]*1fr 1fr/.test(css));
  const score=await readFile(new URL('../src/ScoreboardPage.jsx',import.meta.url),'utf8');
  const home=await readFile(new URL('../src/components/HomeSections.jsx',import.meta.url),'utf8');
  assert.ok(score.includes("<Weekly recap={selected.state === 'final' ? selected.recap : null}"));
  assert.ok(home.includes('<Weekly recap={weekly}'));
});

test('team logos use the shared asset path and a safe fallback for missing or broken images',async()=>{
  const {TeamLogo}=await jsx('../src/components/Standings.jsx','TeamLogo',{React,Section,TableCard:Card});
  const historical=TeamLogo({team:{logo:'logos/Old.png'},size:20});
  assert.equal(historical.props.src,'/logos/Old.png');
  assert.equal(historical.props.width,20);
  assert.equal(TeamLogo({team:{}}).props.src,'/logos/Default.png');
  const target={src:'broken',onerror:()=>{}};
  historical.props.onError({currentTarget:target});
  assert.equal(target.src,'/logos/Default.png');
  assert.equal(target.onerror,null);
});
