import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {transformWithOxc} from 'vite';
import {formatPublicationTime} from '../src/home-data.js';

const source=await readFile(new URL('../src/ScoreboardPage.jsx',import.meta.url),'utf8');
const {code}=await transformWithOxc(source.replace('import.meta.env.BASE_URL',"'/brawl/'"),'ScoreboardPage.jsx',{lang:'jsx',jsx:{runtime:'classic'}});
const body=code.replace(/^import .*;$/gm,'').replace(/export default /g,'').replace(/export /g,'');
const Context=new Function('React','formatPublicationTime','leagueDate',`${body};return ScoreboardContext;`)(React,formatPublicationTime,()=> '2099-01-01');
const render=(status,updatedAt='2026-10-24T12:34:56Z',dates={})=>renderToStaticMarkup(React.createElement(Context,{
  selected:{state:status,matchups:[{status}],...dates},current:{asOfDate:'2026-10-24'},updatedAt}));

test('only an in-progress matchup shows Last updated using recorded data time',()=>{
  const html=render('current');
  assert.ok(html.includes('Last updated:'));
  assert.ok(html.includes('dateTime="2026-10-24T12:34:56Z"'));
  assert.ok(html.includes('10/24/26 08:34:56 AM ET'));
  for(const status of ['final','future','bye','unavailable']) assert.ok(!render(status).includes('Last updated:'));
  assert.ok(!render('current',null).includes('Last updated:'));
  assert.ok(!render('current','invalid').includes('Last updated:'));
});
test('scheduled full dates render for current and future weeks; absent dates are explicit',()=>{
  for(const state of ['current','future','final']) {
    assert.ok(render(state,null,{start:'2026-12-28',end:'2027-01-10'}).includes('2026-12-28 – 2027-01-10'));
  }
  assert.ok(render('future').includes('Schedule dates unavailable.'));
  assert.ok(!render('current').includes('Calendar observed'));
});
test('Scoreboard removes the disclaimer without replacement and keeps existing statuses',()=>{
  assert.ok(!source.includes('Fantasy points shown are actual scores'));
  assert.ok(!source.includes('Scheduled matchups have no score until the week starts'));
  assert.ok(!source.includes('Last published:'));
  assert.ok(source.includes('matchupStatus[match.status]'));
});

test('historical observed dates are explicitly identified',()=>{
  const html=render('final',null,{start:'2025-12-29',end:'2026-01-04',dateRangeKind:'observed'});
  assert.ok(html.includes('Observed dates: 2025-12-29 – 2026-01-04'));
});
