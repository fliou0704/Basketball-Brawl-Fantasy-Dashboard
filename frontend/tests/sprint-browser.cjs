/* Run with NODE_PATH=/private/tmp/brawl-sprint-tools/node_modules against the isolated preview. */
const {chromium}=require('playwright-core');
const assert=require('node:assert/strict');
const base=process.env.BRAWL_URL||'http://127.0.0.1:4176/Basketball-Brawl-Fantasy-Dashboard/';
(async()=>{
 const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
 try {
  const page=await browser.newPage();const errors=[];page.on('pageerror',error=>errors.push(String(error)));
  // Exercise real image-error fallback without depending on the external CDN.
  await page.route('https://a.espncdn.com/**',route=>route.abort());
  const fits=async()=>assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'page width fits viewport');
  const genuine=async selector=>assert.deepEqual(await page.locator(selector).first().evaluate(t=>[getComputedStyle(t).display,getComputedStyle(t.querySelector('thead')).display,getComputedStyle(t.querySelector('tbody tr')).display,getComputedStyle(t.querySelector('tbody td')).display]),['table','table-header-group','table-row','table-cell']);
  for(const width of [375,430,768,1280]) {
   await page.setViewportSize({width,height:1000});
   await page.goto(base+'#/standings');await page.locator('.standings-table tbody tr').first().waitFor();
   const years=await page.getByLabel('Season',{exact:true}).locator('option').allTextContents();
   for(const year of years) {
    await page.getByLabel('Season',{exact:true}).selectOption(year);
    await page.locator('.standings-table').waitFor();
    await genuine('.standings-table');await fits();
    const history=await page.evaluate(async url=>(await(await fetch(url)).json()).data,base+`data/${year}/history.json`);
    if(history.standingsCharts?.ranks.length) {
     await page.waitForFunction(n=>document.querySelectorAll('.rank-progression-chart > text').length===n+1,(history.standingsCharts.rankWeekTicks||history.standingsCharts.weeks).length);
     assert.equal(await page.locator('.scoring-leaders-chart title').count(),0);
     assert.equal(await page.locator('.scoring-leaders-chart image').count(),history.standingsCharts.highWeeks.length);
     const buttons=page.locator('.rank-chart-controls button');await buttons.nth(1).click();assert.equal(await buttons.nth(1).getAttribute('aria-pressed'),'true');
     await page.locator('.rank-progression-chart circle').first().click({force:true});assert.equal(await buttons.nth(1).getAttribute('aria-pressed'),'true');
     await buttons.first().click();assert.equal(await buttons.first().getAttribute('aria-pressed'),'true');
    }
   }
   await page.getByRole('button',{name:/All-Play W-L/}).click();assert.equal(await page.locator('th[aria-sort]').getAttribute('aria-sort'),'descending');
   await page.locator('.standings-table').evaluate(table=>table.parentElement.scrollLeft=0);
   await page.screenshot({path:`/private/tmp/brawl-standings-${width}.png`,fullPage:true});
   await page.goto(base+'#/record-book');await page.getByLabel('Year',{exact:true}).selectOption('All-Time');
   const details=page.locator('.all-time-expandable details');assert.equal(await details.count(),3);await fits();
   for(let i=0;i<3;i++){await details.nth(i).locator('summary').click();await genuine('.record-table');await fits();assert.ok(await details.nth(i).locator('.compact-player-headshot').count()>0);}
   const first=page.locator('.record-table').first();assert.equal(await first.locator('thead th').count(),13);
   const watch=first.locator('.highlights-play').first();assert.equal(await watch.getAttribute('rel'),'noopener noreferrer');assert.ok((await watch.getAttribute('href')).includes('youtube.com/results?search_query='));
   await page.screenshot({path:`/private/tmp/brawl-records-${width}.png`,fullPage:true});
   for(let i=0;i<3;i++)await details.nth(i).locator('summary').click();await fits();
   await page.goto(base+'#/players');await page.getByText('Rankings and free-agent recommendations will appear',{exact:false}).waitFor();await fits();
  }
  // Fixture enables UI validation of the guarded feature without asserting incomplete real data is NBA-wide.
  const owner={teamId:2,teamName:'Fixture team',logo:'logos/Default.png'};
  const players=Array.from({length:160},(_,i)=>({playerId:i+1,name:`Fixture Player ${i+1}`,nbaTeam:'NBA',gp:i===159?1:40,fpts:10000-i*20,fantasyTeam:i>=150?owner:null}));
  players.push({playerId:200,name:'No stats',fpts:null,gp:null,fantasyTeam:owner});
  await page.route('**/data/top-150.json',route=>route.fulfill({json:{schemaVersion:1,years:[2027],seasons:{2027:{completePool:true,maxTeamGames:82,ownershipAvailable:true,players}}}}));
  for(const width of [375,430,768,1280]) {
   await page.setViewportSize({width,height:1000});await page.goto(base+'#/players');await page.reload();await page.locator('.top150-table').waitFor();
   await genuine('.top150-table');await fits();assert.equal(await page.locator('.top150-free-agent').count(),150);assert.equal(await page.locator('.top150-table tbody tr').count(),162);
   await page.getByRole('button',{name:'FPTS/Game',exact:true}).click();assert.equal(await page.getByRole('button',{name:'FPTS/Game',exact:true}).getAttribute('aria-pressed'),'true');
   assert.ok((await page.locator('.top150-table').innerText()).includes('NQ'));await fits();
   await page.screenshot({path:`/private/tmp/brawl-top150-fixture-${width}.png`,fullPage:true});
  }
  // Home and Standings share row values for the same displayed season.
  await page.goto(base);await page.locator('.standings-table').waitFor();
  const title=await page.locator('main h1').innerText();const year=title.match(/\d{4}/)[0];const home=await page.locator('.standings-table').innerText();await fits();
  await page.goto(base+'#/standings');await page.getByLabel('Season',{exact:true}).selectOption(year);await page.waitForFunction(text=>document.querySelector('.standings-table')?.innerText===text,home);
  assert.deepEqual(errors,[]);console.log('PASS: 4 viewport sizes, every season, collapsed/expanded records, chart interactions, fallback images, guarded/fixture Top 150, Home parity.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
