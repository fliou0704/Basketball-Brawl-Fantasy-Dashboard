import test from 'node:test';
import assert from 'node:assert/strict';
import {calendarSeason,scoringDate,matchupForDate,matchupRange,matchupDates,formatCalendarDate,formatCalendarRange} from '../src/fantasy-calendar.js';

test('verified exported rows answer reusable calendar lookups with unavailable fallbacks',()=>{
 const data={seasons:[{season:2027,verified:true,days:[{period:7,date:'2026-10-26',week:2},{period:8,date:'2026-10-27',week:2}],weeks:[{week:2,start:'2026-10-26',end:'2026-11-01'}]}]};
 assert.equal(scoringDate(data,2027,8),'2026-10-27');
 assert.equal(matchupForDate(data,2027,'2026-10-27'),2);
 assert.equal(matchupRange(data,2027,2).end,'2026-11-01');
 assert.deepEqual(matchupDates(data,2027,2),['2026-10-26','2026-10-27']);
 assert.equal(scoringDate(data,2027,99),null);
 assert.equal(calendarSeason(data,2026),null);
 assert.deepEqual(matchupDates(null,2027,2),[]);
});
test('date labels preserve civil dates in every host zone, including year boundaries',()=>{
 const old=process.env.TZ;
 try {for(const zone of ['UTC','America/New_York','America/Los_Angeles','Asia/Tokyo']) {
  process.env.TZ=zone;
  assert.equal(formatCalendarDate('2026-10-26','long'),'Monday, October 26');
  assert.equal(formatCalendarRange('2026-10-26','2026-11-01'),'Oct 26 – Nov 1, 2026');
  assert.equal(formatCalendarRange('2026-12-28','2027-01-03'),'Dec 28, 2026 – Jan 3, 2027');
 }} finally {if(old===undefined)delete process.env.TZ;else process.env.TZ=old;}
 assert.equal(formatCalendarDate('2026-02-30'),'Date unavailable');
 assert.equal(formatCalendarRange(null,null),'Schedule dates unavailable');
});
