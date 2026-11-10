// Exercise real polling/effects with a controlled clock, delayed responses and update failures.
const {chromium}=require('playwright');
const fs=require('node:fs/promises');
const path=require('node:path');
const assert=require('node:assert/strict');
(async()=>{
 const root=process.env.BRAWL_EXPORT || '/private/tmp/brawl-redesign-live';
 const base=process.env.BRAWL_URL || 'http://127.0.0.1:5173/Basketball-Brawl-Fantasy-Dashboard/';
 const scoreboard=JSON.parse(await fs.readFile(path.join(root,'scoreboard.json'),'utf8'));
 const year=scoreboard.current.season,week=scoreboard.current.week;
 const selected=scoreboard.seasons.find(s=>s.season===year).weeks.find(w=>w.week===week);
 const match=selected.matchups.find(m=>m.teams.length===2);
 const key=match.teams.map(t=>t.teamId).sort((a,b)=>a-b).join('-');
 const detailBase=JSON.parse(await fs.readFile(path.join(root,selected.detailPath),'utf8'));
 const detail=detailBase.matchups.find(m=>m.key===key);
 const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
 for(const width of [1280,390,320]){
  const page=await browser.newPage({viewport:{width,height:1000}});let documents=0,scoreboardReads=0,detailReads=0,delay=false,fail=false,failManifest=false,concurrent=0,maxConcurrent=0;
  const errors=[];page.on('pageerror',e=>errors.push(String(e)));page.on('request',r=>{if(r.resourceType()==='document')documents++;});
  await page.addInitScript(()=>{window.__intervals=[];const original=window.setInterval;window.setInterval=(callback,ms,...args)=>{window.__intervals.push({callback,ms});return original(callback,ms,...args);};window.__timeOffset=0;const now=Date.now;Date.now=()=>now()+window.__timeOffset;window.__hashes=0;window.addEventListener('hashchange',()=>window.__hashes++);});
  await page.route('**/data/**',async route=>{
   const relative=decodeURIComponent(new URL(route.request().url()).pathname.split('/data/')[1]);
   if(relative==='scoreboard.json'){
    scoreboardReads++;concurrent++;maxConcurrent=Math.max(maxConcurrent,concurrent);
    await new Promise(resolve=>setTimeout(resolve,100));concurrent--;
    return failManifest?route.fulfill({status:503,body:'Temporarily unavailable'}):route.fulfill({json:scoreboard});
   }
   if(relative===selected.detailPath){
    detailReads++;if(delay)await new Promise(resolve=>setTimeout(resolve,600));
    return fail?route.fulfill({status:503,body:'Temporarily unavailable'}):route.fulfill({json:detailBase});
   }
   const file=path.resolve(root,relative);if(!file.startsWith(root+'/'))return route.abort();
   try{const body=await fs.readFile(file);if(['matchup-opportunities.json','nba-schedule.json'].includes(relative)){const value=JSON.parse(body);value.updatedAt=scoreboard.updatedAt;await route.fulfill({json:value});}else await route.fulfill({body,contentType:'application/json'});}catch{await route.continue();}
  });
  await page.goto(base+`#/scoreboard?season=${year}&week=${week}&match=${key}`);
  const dropdown=page.getByLabel('Lineup view',{exact:true});await dropdown.waitFor();
  // Validate the real Summary output, independently on each side, before choosing a date.
  const summary=detail.summaryLineup.filter(p=>p.eligible);
  const teams=[match.awayTeamId,match.homeTeamId];
  for(let i=0;i<teams.length;i++){
   const ids=summary.filter(p=>p.teamId===teams[i]).sort((a,b)=>b.points-a.points||a.playerId-b.playerId).map(p=>p.playerId);
   const actual=await page.locator(`.box-lineup-group`).first().locator(`.box-player.${i===0?'away':'home'}`).evaluateAll(ns=>ns.map(n=>Number(n.dataset.playerId)));
   assert.deepEqual(actual,ids);
  }
  const date=await dropdown.locator('option').nth(1).getAttribute('value');await dropdown.selectOption(date);
  await page.evaluate(()=>{document.querySelector('.box-lineup-select').scrollIntoView();window.__select=document.querySelector('.box-lineup-select select');window.__removed=0;new MutationObserver(records=>{for(const r of records)for(const n of r.removedNodes)if(n.nodeType===1&&(n===window.__select||n.contains(window.__select)))window.__removed++;}).observe(document.querySelector('main'),{childList:true,subtree:true});});
  const scroll=await page.evaluate(()=>scrollY);
  const stable=async()=>{assert.equal(await dropdown.inputValue(),date);assert.equal(await page.evaluate(()=>window.__select===document.querySelector('.box-lineup-select select')),true);assert.equal(await page.evaluate(()=>window.__removed),0);assert.ok(Math.abs(await page.evaluate(()=>scrollY)-scroll)<=2,'scroll retained');};
  // Changing Summary/date uses the same dropdown and preserves the viewport.
  await dropdown.selectOption('summary');assert.ok(Math.abs(await page.evaluate(()=>scrollY)-scroll)<=2);
  await dropdown.selectOption(date);await stable();
  await page.waitForTimeout(500);await stable();
  // Rapid focus events are throttled. Normal unchanged five-minute polling reads only the manifest.
  let count=scoreboardReads;await page.evaluate(()=>{for(let i=0;i<5;i++)window.dispatchEvent(new Event('focus'));});await page.waitForTimeout(250);assert.equal(scoreboardReads,count);
  let reads=detailReads;
  await page.evaluate(()=>window.__intervals.find(p=>p.ms===300000).callback());await page.waitForTimeout(350);assert.equal(detailReads,reads);await stable();
  // Mature focus bursts coalesce into one request; unchanged data never resets the detail.
  count=scoreboardReads;await page.evaluate(()=>{window.__timeOffset+=61000;for(let i=0;i<5;i++)window.dispatchEvent(new Event('focus'));});await page.waitForTimeout(350);assert.equal(scoreboardReads,count+1);assert.equal(detailReads,reads);assert.equal(maxConcurrent,1);await stable();
  // A failed manifest check must also retain the page and avoid a detail refetch.
  failManifest=true;await page.evaluate(()=>window.__intervals.find(p=>p.ms===300000).callback());await page.waitForTimeout(350);await stable();assert.equal(detailReads,reads);
  failManifest=false;await page.evaluate(()=>window.__intervals.find(p=>p.ms===300000).callback());await page.waitForTimeout(350);await stable();
  // A real score update must refresh the details, keeping the selected DOM/scroll during the request.
  const old=match.actualScores[0];match.actualScores[0]=old+1;
  detailBase.updatedAt=scoreboard.updatedAt='2099-01-01T00:00:00Z';delay=true;
  await page.evaluate(()=>window.__intervals.find(p=>p.ms===300000).callback());await page.waitForTimeout(300);await stable();
  await page.waitForTimeout(900);await stable();assert.equal(detailReads,reads+1);
  const home=page.locator('.facing-team.home .facing-points');assert.ok((await home.innerText()).includes((old+1).toLocaleString('en-US')));
  // Failed updates retain the previous complete snapshot, then recover without a remount.
  detailBase.updatedAt=scoreboard.updatedAt='2099-01-02T00:00:00Z';match.actualScores[0]=old+2;fail=true;
  await page.evaluate(()=>window.__intervals.find(p=>p.ms===300000).callback());await page.waitForTimeout(1000);await stable();await page.getByText('Refresh failed. Showing the last complete matchup snapshot;',{exact:false}).waitFor();
  assert.ok((await home.innerText()).includes((old+1).toLocaleString('en-US')));
  fail=false;
  await page.evaluate(()=>window.__intervals.find(p=>p.ms===300000).callback());await page.waitForTimeout(1000);await stable();assert.ok((await home.innerText()).includes((old+2).toLocaleString('en-US')));
  assert.equal(documents,1);assert.equal(await page.evaluate(()=>window.__hashes),0);assert.deepEqual(errors,[]);
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth)<=width);
  await page.screenshot({path:`/private/tmp/matchup-polish-${width}.png`,fullPage:true});
  console.log('PASS',width,'summary rank, idle/focus/poll, unchanged requests, changed/failed/recovered data, retained select/scroll/DOM, no navigation, overflow');await page.close();
 }
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
