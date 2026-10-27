// Browser regressions against Vite. Serve disposable exports without replacing local artifacts.
const {chromium}=require('playwright');
const fs=require('node:fs/promises');
const path=require('node:path');
const assert=require('node:assert/strict');
(async()=>{
 const root=process.env.BRAWL_EXPORT || '/private/tmp/brawl-batch-b-live-export';
 const base=process.env.BRAWL_URL || 'http://127.0.0.1:5173/Basketball-Brawl-Fantasy-Dashboard/';
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
 const page=await browser.newPage();const errors=[];
 page.on('pageerror',e=>errors.push(String(e)));
 await page.route('**/data/**',async route=>{
  const relative=decodeURIComponent(new URL(route.request().url()).pathname.split('/data/')[1]);
  const file=path.resolve(root,relative);
  if(!file.startsWith(root+'/'))return route.abort();
  try{await route.fulfill({body:await fs.readFile(file),contentType:'application/json'});}catch{await route.continue();}
 });
 const noOverflow=async width=>{const size=await page.evaluate(()=>document.documentElement.scrollWidth);if(size>width)console.log('Overflow diagnostic',page.url(),await page.evaluate(()=>[...document.querySelectorAll('main *')].filter(e=>e.getBoundingClientRect().right>innerWidth).slice(0,8).map(e=>({tag:e.tagName,cls:e.className,text:e.textContent.slice(0,60),right:e.getBoundingClientRect().right}))));assert.ok(size<=width,`overflow at ${width} ${page.url()}`);};
 for(const width of [1280,390,320]){
  await page.setViewportSize({width,height:1000});
  await page.goto(base+'#/scoreboard?season=2027&week=2');
  await page.locator('.scoreboard-match').first().waitFor();
  assert.equal(await page.locator('.scoreboard-match').count(),5);
  const href=await page.locator('.scoreboard-match').first().getAttribute('href');
  await page.locator('.scoreboard-match').first().click();
  await page.getByText('Daily totals reconcile to the scoreboard snapshot.',{exact:false}).waitFor();
  assert.equal(new URL(page.url()).hash,href);
  await noOverflow(width);
  await page.getByRole('button',{name:'Cumulative Score',exact:true}).click();
  await page.getByRole('button',{name:'Daily',exact:true}).click();
  await page.getByRole('button',{name:'Players',exact:true}).click();
  await page.getByRole('heading',{name:'Matchup contributors'}).waitFor();
  await noOverflow(width);
  await page.screenshot({path:`/private/tmp/matchup-players-${width}.png`,fullPage:true});
  await page.reload();
  await page.getByText('Daily totals reconcile to the scoreboard snapshot.',{exact:false}).waitFor();
  await page.goBack();await page.locator('.scoreboard-match').first().waitFor();
  await page.goForward();await page.getByText('Daily totals reconcile to the scoreboard snapshot.',{exact:false}).waitFor();
  for(const [year,week,kind] of [[2026,1,'historical'],[2026,17,'extended'],[2026,21,'playoffs'],[2027,3,'future']]){
   await page.goto(base+`#/scoreboard?season=${year}&week=${week}`);
   await page.locator('.scoreboard-match').first().waitFor();
   await page.locator('.scoreboard-match').first().click();
   await page.getByRole('heading',{name:'Scoring timeline'}).waitFor();
   await noOverflow(width);
   if(kind==='extended'){
    assert.equal(await page.locator('.matchup-day-select option').count(),14);
    await page.locator('.matchup-day-select select').selectOption('13');
    await page.getByRole('heading',{name:'2026-02-22 · Period 125',exact:true}).waitFor();
    await page.screenshot({path:`/private/tmp/matchup-extended-${width}.png`,fullPage:true});
   }
   if(kind==='future'){
    assert.equal(await page.locator('.match-team strong').allTextContents().then(x=>x.join(',')),'—,—');
    await page.getByText('No recorded scoring periods yet.',{exact:true}).first().waitFor();
   }
  }
  await page.goto(base+'#/scoreboard?season=2026&week=1&match=999-1000');
  await page.getByText('This matchup is unavailable.',{exact:false}).waitFor();
  await noOverflow(width);
  for(const route of ['','#/standings','#/teams/1']){
   await page.goto(base+route);await page.locator('main h1').waitFor();if(route!=='#/teams/1')await noOverflow(width);
  }
  console.log('PASS',width,'current, historical, extended, playoffs, future, tabs, refresh, back/forward, unknown, Home, standings, team');
 }
 assert.deepEqual(errors,[]);
 await browser.close();
})().catch(error=>{console.error(error);process.exit(1);});
