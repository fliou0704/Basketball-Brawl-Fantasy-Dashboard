// Run against a built Vite preview. Uses real HTTP and checked-in ranking assets.
// PLAYWRIGHT_CORE_PATH may point at an existing playwright-core installation.
const {chromium}=require(process.env.PLAYWRIGHT_CORE_PATH||'playwright-core');
const assert=require('node:assert/strict');
const origin=process.env.TOP150_PREVIEW_URL||'http://127.0.0.1:4174/Basketball-Brawl-Fantasy-Dashboard/';
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
 try{
  if(process.env.TOP150_BASELINE_URL){
   const page=await browser.newPage();await page.goto(process.env.TOP150_BASELINE_URL+'#/players',{waitUntil:'domcontentloaded'});
   await page.getByText('A verified complete NBA player pool is unavailable for this season.').waitFor();
   assert.equal(await page.locator('[data-ranking-id]').count(),0);
   console.log('Original Players landing failure reproduced with real index HTTP response');await page.close();
  }
  for(const width of [375,1280]){
   const page=await browser.newPage({viewport:{width,height:900}}),errors=[],responses=[];
   page.on('pageerror',e=>errors.push(e.message));
   page.on('response',r=>{if(/\/data\/(top-150|top150\/)/.test(r.url()))responses.push([new URL(r.url()).pathname,r.status()]);});
   for(const route of ['/players','/top-150']){
    await page.goto(origin+'#'+route,{waitUntil:'domcontentloaded'});await page.locator('.top150-table tbody tr').first().waitFor();
    assert.equal(await page.locator('.top150-table').first().locator('tbody tr').count(),150);
    assert.equal(await page.locator('main').count(),1);
   }
   const snapshot=await page.evaluate(async base=>(await fetch(base+'data/top150/2027.json')).json(),origin);
   assert.equal(snapshot.players.filter(p=>p.fantasyTeam).length,163);
   for(const mode of ['Total FPTS','FPTS/Game']){
    await page.getByRole('button',{name:mode,exact:true}).click();
    assert.equal(await page.locator('.top150-table').first().locator('tbody tr').count(),150);
    const ids=await page.locator('[data-ranking-id]').evaluateAll(rows=>rows.map(r=>Number(r.dataset.rankingId)));
    assert.equal(snapshot.players.filter(p=>p.fantasyTeam&&ids.includes(p.playerId)).length,163);
   }
   await page.getByLabel('Fantasy team',{exact:true}).selectOption('FA');
   const ids=await page.locator('.top150-table').first().locator('[data-ranking-id]').evaluateAll(rows=>rows.map(r=>Number(r.dataset.rankingId)));
   assert.ok(ids.length>0&&ids.every(id=>!snapshot.players.find(p=>p.playerId===id).fantasyTeam));
   await page.getByLabel('Fantasy team',{exact:true}).selectOption('');
   await page.getByLabel('Search players').fill('zzzz-no-player');await page.getByText('No players match these filters.').first().waitFor();
   await page.getByLabel('Search players').fill('');
   await page.getByLabel('Season',{exact:true}).selectOption('2023');
   await page.getByText(/Historical fantasy ownership unavailable/).waitFor();
   await page.locator('.top150-table tbody tr').first().waitFor();
   assert.ok(await page.getByLabel('Fantasy team',{exact:true}).isDisabled());
   await page.locator('.player-cell a').first().click();await page.locator('.ranking-game-log tbody tr').first().waitFor();
   await page.getByRole('button',{name:'Close game log'}).click();
   await page.getByLabel('Season',{exact:true}).selectOption('2027');
   await page.locator('.top150-table tbody tr').first().waitFor();
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   assert.ok(responses.some(([p,s])=>p.endsWith('/top-150.json')&&s===200));
   assert.ok(responses.some(([p,s])=>p.endsWith('/top150/2027.json')&&s===200));
   assert.deepEqual(errors,[]);console.log(JSON.stringify({width,rows:150,roster:163,filters:true,seasonSwitch:true,gameLog:true,responses}));
   await page.close();
  }
  const smoke=await browser.newPage();
  for(const route of ['', '/standings', '/teams/1', '/h2h/historical', '/record-book', '/scoreboard']){
   await smoke.goto(origin+'#'+route,{waitUntil:'domcontentloaded'});await smoke.locator('main').waitFor();await smoke.waitForTimeout(800);assert.equal(await smoke.getByRole('alert').count(),0);console.log('Dashboard smoke:',route||'Home');
  }
  await smoke.close();
  // Fault injection is separate from the real-file acceptance above.
  for(const [label,response,expected] of [
   ['missing',{status:404,body:'Not found'},/could not be loaded/],
   ['html',{status:200,body:'<html>not JSON</html>'},/could not be read/],
   ['schema',{status:200,json:{schemaVersion:99}},/could not be read/],
   ['empty',{status:200,json:{schemaVersion:1,completePool:true,players:[],maxTeamGames:10}},/No recorded player statistics/],
   ['coverage',{status:200,json:{schemaVersion:1,completePool:false,players:[{playerId:1}],maxTeamGames:10}},/coverage checks/]
  ]){
   const p=await browser.newPage();await p.route('**/data/top150/*.json*',r=>r.fulfill(response));await p.goto(origin+'#/players',{waitUntil:'domcontentloaded'});await p.getByRole('alert').filter({hasText:expected}).waitFor();
   assert.equal(await p.locator('[data-ranking-id]').count(),0);console.log('Error state:',label);await p.close();
  }
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
