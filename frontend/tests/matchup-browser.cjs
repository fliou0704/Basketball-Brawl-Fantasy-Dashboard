// BRAWL_EXPORT selects fresh disposable exports; BRAWL_LIVE=1 checks deployed data.
const {chromium}=require('playwright');
const fs=require('node:fs/promises');
const path=require('node:path');
const assert=require('node:assert/strict');
(async()=>{
 const root=process.env.BRAWL_EXPORT || '/private/tmp/brawl-redesign-live';
 const base=process.env.BRAWL_URL || 'http://127.0.0.1:5173/Basketball-Brawl-Fantasy-Dashboard/';
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
 const page=await browser.newPage();const errors=[];
 page.on('pageerror',e=>errors.push(String(e)));
 if(!process.env.BRAWL_LIVE)await page.route('**/data/**',async route=>{
  const relative=decodeURIComponent(new URL(route.request().url()).pathname.split('/data/')[1]);
  const file=path.resolve(root,relative);if(!file.startsWith(root+'/'))return route.abort();
  try{await route.fulfill({body:await fs.readFile(file),contentType:'application/json'});}catch{await route.continue();}
 });
 const noOverflow=async width=>assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth)<=width,`overflow at ${width}: ${page.url()}`);
 await page.goto(base+'#/scoreboard');
 const data=await page.evaluate(async base=>await (await fetch(base+'data/scoreboard.json')).json(),base);
 const current=data.current;
 const cases=[[current.season,current.week,'current'],[2026,1,'historical'],[2026,17,'extended'],[2026,21,'playoffs'],[current.season,current.week+1,'future']];
 for(const width of [1280,390,320]){
  await page.setViewportSize({width,height:1000});
  for(const [year,week,kind] of cases){
   await page.goto(base+`#/scoreboard?season=${year}&week=${week}`);
   await page.locator('.scoreboard-match').first().waitFor();
   assert.equal(await page.getByLabel('Season',{exact:true}).count(),1);
   const selected=data.seasons.find(s=>s.season===year).weeks.find(w=>w.week===week);
   // Select an actual two-sided playoff pairing, retaining separate bye coverage below.
   const match=selected.matchups.find(m=>m.teams.length===2);
   const key=match.teams.map(t=>t.teamId).sort((a,b)=>a-b).join('-');
   const href=`#/scoreboard?season=${year}&week=${week}&match=${key}`;
   await page.locator(`a.scoreboard-match[href="${href}"]`).click();
   await page.getByRole('heading',{name:'Head-to-head scoring breakdown',exact:true}).waitFor();
   assert.equal(await page.getByLabel('Season',{exact:true}).count(),0);
   assert.equal(await page.getByLabel('Week',{exact:true}).count(),0);
   assert.equal(await page.locator('.matchup-box-score section.home-section').count(),4);
   assert.equal(await page.getByRole('navigation',{name:'Matchup views'}).count(),0);
   assert.equal(await page.locator('svg.matchup-chart').count(),0);
   const displayed=await page.locator('.facing-team').evaluateAll(nodes=>nodes.map(n=>Number(n.dataset.teamId)));
   assert.deepEqual(displayed,[match.awayTeamId,match.homeTeamId]);
   const back=page.getByRole('link',{name:`← ${year} Week ${week} Matchups`,exact:true});
   assert.equal(await back.getAttribute('href'),`#/scoreboard?season=${year}&week=${week}`);
   assert.equal(await page.getByLabel('Lineup view',{exact:true}).inputValue(),'summary');
   const options=page.locator('.box-lineup-select option');
   if(kind==='extended')assert.equal(await options.count(),15);
   if(await options.count()>1){
    await page.getByLabel('Lineup view',{exact:true}).selectOption(await options.nth(1).getAttribute('value'));
    await page.getByText(kind==='future'?'Manager-selected future lineup unavailable.':'Complete daily lineup unavailable.',{exact:false}).waitFor();
    await noOverflow(width);
    await page.getByLabel('Lineup view',{exact:true}).selectOption('summary');
   }
   if(kind==='future'){
    assert.deepEqual(await page.locator('.facing-points').evaluateAll(ns=>ns.map(n=>n.childNodes[0].textContent)),['—','—']);
    assert.equal(await page.locator('.daily-margin').count(),0);
   }
   await noOverflow(width);
   assert.ok(await page.locator('.daily-box-table tbody th').first().evaluate(n=>n.getBoundingClientRect().width)>=100,'team identity column must stay readable');
   if(width<720&&kind!=='future'){
    assert.ok(await page.locator('.daily-box-scroll').evaluate(n=>n.scrollWidth>n.clientWidth),'daily table should scroll within its card');
   }
   if(kind==='current'){
    const playerDetails=page.locator('.opportunity-player-details details');
    if(await playerDetails.count()){
     await playerDetails.first().locator('summary').click();
     await page.locator('.opportunity-player').first().waitFor();await noOverflow(width);
     await playerDetails.first().locator('summary').click();
    }
   }
   await page.screenshot({path:`/private/tmp/redesign-${kind}-${width}.png`,fullPage:true});
   await page.reload();await page.getByRole('heading',{name:'Head-to-head scoring breakdown',exact:true}).waitFor();
   await page.getByRole('link',{name:`← ${year} Week ${week} Matchups`,exact:true}).click();
   await page.locator('.scoreboard-match').first().waitFor();
   await page.goBack();await page.getByRole('heading',{name:'Head-to-head scoring breakdown',exact:true}).waitFor();
   await page.goForward();await page.locator('.scoreboard-match').first().waitFor();
  }
  // H2H's shared breakdown must preserve its existing expansion behavior.
  await page.goto(base+'#/h2h/historical');
  await page.locator('#h2h-team-0').selectOption('1');await page.locator('#h2h-team-1').selectOption('17');
  await page.locator('.result-row').first().click();await page.locator('.matchup-details .player-sides').waitFor();
  await noOverflow(width);
  await page.goto(base+'#/scoreboard?season=2026&week=1&match=999-1000');
  await page.getByText('This matchup is unavailable.',{exact:false}).waitFor();await noOverflow(width);
  console.log('PASS',width,'away/home, four sections, summary/date, current, historical, extended, playoffs, future, opportunities, direct URL/reload/back/forward, H2H, overflow');
 }
 assert.deepEqual(errors,[]);await browser.close();
})().catch(error=>{console.error(error);process.exit(1);});
