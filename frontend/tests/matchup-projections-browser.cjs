const {chromium}=require('playwright');
const fs=require('node:fs/promises');
const path=require('node:path');
const assert=require('node:assert/strict');
(async()=>{
 const root=process.env.BRAWL_EXPORT || '/private/tmp/brawl-projections-live';
 const base=process.env.BRAWL_URL || 'http://127.0.0.1:4173/Basketball-Brawl-Fantasy-Dashboard/';
 const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
 const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 if(!process.env.BRAWL_LIVE)await page.route('**/data/**',async route=>{
  const relative=decodeURIComponent(new URL(route.request().url()).pathname.split('/data/')[1]);
  const file=path.resolve(root,relative);if(!file.startsWith(root+'/'))return route.abort();
  try{await route.fulfill({body:await fs.readFile(file),contentType:'application/json'});}catch{await route.continue();}
 });
 await page.goto(base+'#/scoreboard');
 const {scoreboard,opps}=await page.evaluate(async base=>({scoreboard:await(await fetch(base+'data/scoreboard.json')).json(),opps:await(await fetch(base+'data/matchup-opportunities.json')).json()}),base);
 const year=scoreboard.current.season,number=scoreboard.current.week;
 const season=scoreboard.seasons.find(s=>s.season===year);
 const cup=season.weeks.find(w=>w.matchups.some(m=>m.teams.length===2)&&Object.values(opps.weeks[String(w.week)]||{}).some(t=>t.projection?.days.some(d=>d.additionalTBD)));
 const fmt=n=>n==null?'Unavailable':n.toLocaleString('en-US',{maximumFractionDigits:1});
 const open=async(y,w)=>{
  const selected=scoreboard.seasons.find(s=>s.season===y).weeks.find(v=>v.week===w);
  const match=selected.matchups.find(m=>m.teams.length===2);const key=match.teams.map(t=>t.teamId).sort((a,b)=>a-b).join('-');
  await page.goto(base+`#/scoreboard?season=${y}&week=${w}&match=${key}`);
  await page.getByRole('heading',{name:'Head-to-head scoring breakdown',exact:true}).waitFor();
  return match;
 };
 const overflow=async width=>assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth)<=width,`overflow at ${width}`);
 for(const width of [1280,390,320]){
  await page.setViewportSize({width,height:1000});
  const match=await open(year,number),teamIds=[match.awayTeamId,match.homeTeamId];
  for(let i=0;i<2;i++){
   const projection=opps.weeks[String(number)][String(teamIds[i])].projection;
   assert.ok(projection,'server exported projections');
   if(projection.remaining!=null){
    const index=match.teams.findIndex(t=>t.teamId===teamIds[i]);
    const text=await page.locator('.estimate-team').nth(i).innerText();
    assert.ok(text.includes(fmt(projection.remaining)));assert.ok(text.includes(fmt(projection.remaining+match.actualScores[index])));
   }
  }
  assert.equal(await page.locator('.matchup-box-score section.home-section').count(),4);
  await overflow(width);
  await page.screenshot({path:`/private/tmp/projections-scorecard-${width}.png`,fullPage:true});
  const date=opps.weeks[String(number)][String(teamIds[0])].projection.days.find(d=>d.players.length)?.date;
  if(date){
   await page.getByLabel('Lineup view',{exact:true}).selectOption(date);
   await page.getByRole('heading',{name:`Optimal projected lineup`,exact:false}).waitFor();
   for(let i=0;i<2;i++){
    const expected=opps.weeks[String(number)][String(teamIds[i])].projection.days.find(d=>d.date===date)?.players||[];
    const actual=await page.locator(`.projected-lineups .box-player.${i===0?'away':'home'}[data-projected-player]`).evaluateAll(ns=>ns.map(n=>Number(n.dataset.projectedPlayer)));
    assert.deepEqual(actual.sort((a,b)=>a-b),expected.map(p=>p.playerId).sort((a,b)=>a-b));
    assert.ok(expected.filter(p=>p.selected).length<=10);
   }
   await overflow(width);
   await page.screenshot({path:`/private/tmp/projections-players-${width}.png`,fullPage:true});
  }
  await page.getByLabel('Lineup view',{exact:true}).selectOption('summary');
  const potential=page.locator('.potential-points');
  if(await potential.count()){
   await potential.locator('summary').click();await page.getByText('Lineup efficiency',{exact:true}).first().waitFor();
   assert.ok((await potential.innerText()).includes('Unavailable'));await overflow(width);
  }
  await open(2026,17);assert.equal(await page.locator('.matchup-estimates').count(),0);
  await page.locator('.potential-points summary').click();await overflow(width);
  await open(year,number+1);await page.locator('.matchup-estimates').waitFor();await overflow(width);
  assert.deepEqual(await page.locator('.facing-points').evaluateAll(ns=>ns.map(n=>n.childNodes[0].textContent)),['—','—']);
  if(cup){
   await open(year,cup.week);
   await page.getByText('Additional NBA Cup dates or game statuses are unresolved;',{exact:false}).first().waitFor();
   assert.ok((await page.locator('.daily-projection').allTextContents()).some(t=>t.includes('TBD')));
   await overflow(width);
  }
  console.log('PASS',width,'actual+remaining totals, all scheduled players, optimal cap, historical missing evidence, future actuals, Cup TBD, no extra section, overflow');
 }
 assert.deepEqual(errors,[]);await browser.close();
})().catch(error=>{console.error(error);process.exit(1)});
