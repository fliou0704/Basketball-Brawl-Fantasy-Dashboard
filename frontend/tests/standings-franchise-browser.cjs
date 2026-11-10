const {chromium}=require('playwright');
const fs=require('node:fs/promises');
const path=require('node:path');
const assert=require('node:assert/strict');
(async()=>{
 const root=process.env.BRAWL_EXPORT||'/private/tmp/brawl-improvements-export';
 const base=process.env.BRAWL_URL||'http://127.0.0.1:4175/Basketball-Brawl-Fantasy-Dashboard/';
 const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
 try{
  const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  if(!process.env.BRAWL_LIVE)await page.route('**/data/**',async route=>{
   const relative=decodeURIComponent(new URL(route.request().url()).pathname.split('/data/')[1]);
   const file=path.resolve(root,relative);if(!file.startsWith(root+'/'))return route.abort();
   try{await route.fulfill({body:await fs.readFile(file),contentType:'application/json'});}catch{await route.continue();}
  });
  const get=async name=>page.evaluate(async({base,name})=>await(await fetch(base+'data/'+name)).json(),{base,name});
  for(const width of (process.env.BRAWL_WIDTHS||'1280,390,320').split(',').map(Number)){
   await page.setViewportSize({width,height:1000});await page.goto(base+'#/standings');
   await page.getByRole('heading',{name:'All-Play Standings',exact:true}).waitFor();
   const manifest=await get('scoreboard.json');
   for(const season of manifest.seasons){
    await page.getByLabel('Season',{exact:true}).selectOption(String(season.season));
    const heading=page.getByRole('heading',{name:'All-Play Standings',exact:true});await heading.waitFor();
    const history=(await get(`${season.season}/history.json`)).data;
    await page.waitForFunction(({count})=>document.querySelectorAll('.scoring-leaders-chart > text').length===count+2,{count:history.standingsCharts.scoringWeekTicks.length});
    assert.equal(history.standingsCharts.scoringWeekTicks.length,season.weeks.filter(w=>w.phase==='regular').length);
    assert.equal(history.allPlay.teams.length,10);
    assert.equal(history.allPlay.teams.reduce((n,t)=>n+t.wins,0),history.allPlay.teams.reduce((n,t)=>n+t.losses,0));
    assert.ok(history.standingsCharts.highWeeks.every(b=>b.width<40));
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth)<=width);
   }
   await page.screenshot({path:`/private/tmp/standings-improvements-${width}.png`,fullPage:true});
   await page.goto(base+'#/teams/2');await page.getByRole('heading',{name:'Overview',exact:true}).waitFor();
   await page.getByLabel('Season',{exact:true}).selectOption('Summary');
   await page.getByRole('heading',{name:'Franchise Trends',exact:true}).waitFor();
   const payload=await get('team-stats/2.json');
   for(const [i,key] of ['fpts','regularRank','fpPerStart'].entries()){
    const figure=page.locator('.franchise-trend').nth(i);
    for(const mode of Object.keys(payload.franchise.trendViews[key])){
     await figure.getByRole('button',{name:mode[0].toUpperCase()+mode.slice(1),exact:true}).click();
     const chart=payload.franchise.trendViews[key][mode];
     await page.waitForFunction(({i,label,count})=>{const figure=document.querySelectorAll('.franchise-trend')[i];return figure?.querySelector('svg')?.getAttribute('aria-label')===label&&figure.querySelectorAll('circle').length===count;},{i,label:chart.label,count:chart.points.filter(p=>p.value!=null).length});
     assert.equal(await figure.locator('circle').count(),chart.points.filter(p=>p.value!=null).length);
     assert.ok(await figure.locator('text').count()<40,'ticks remain sparse');
     if(chart.points.some(p=>p.value!=null)){
      await figure.locator('circle').last().focus();assert.match(await figure.locator('.franchise-hover').innerText(),/Week/);
     }
     assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth)<=width);
    }
   }
   const seasons=Object.values(payload.seasons).filter(Boolean),metrics=seasons.map(s=>s.performance.season);
   const starts=metrics.reduce((n,m)=>n+m.starts,0),points=metrics.reduce((n,m)=>n+m.fpts,0);
   assert.equal(payload.franchise.totals.fpPerStart,Math.round(points/starts*100)/100);
   for(const season of seasons)for(const metric of Object.values(season.performance.weeks))if(metric.available&&metric.starts)assert.ok(Math.abs(metric.fpPerStart-metric.fpts/metric.starts)<=.00501,'rate rounded to two decimals');
   await page.locator('.franchise-score-audit summary').click();assert.ok((await page.locator('.franchise-score-audit').innerText()).includes('1,802'));
   await page.screenshot({path:`/private/tmp/franchise-improvements-${width}.png`,fullPage:true});
   const scoreboard=await get('scoreboard.json');const week=scoreboard.seasons.find(s=>s.season===2023).weeks.find(w=>w.week===21);
   const match=week.matchups.find(m=>m.teams.some(t=>t.teamId===2));const key=match.teams.map(t=>t.teamId).sort((a,b)=>a-b).join('-');
   await page.goto(base+`#/scoreboard?season=2023&week=21&match=${key}`);
   await page.locator('.score-difference').first().waitFor();assert.match(await page.locator('.score-difference').first().innerText(),/1,80[12]/);
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth)<=width);
   console.log('PASS',width,'all seasons all-play/full week axes, all chart modes/date hover, FP/Start reconciliation, scoring discrepancy context, overflow');
  }
  const quality=await get('data-quality.json');for(const year of [2023,2024,2025,2026])assert.equal(quality.seasons[year].missing3PA,false);
  assert.deepEqual(errors,[]);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
