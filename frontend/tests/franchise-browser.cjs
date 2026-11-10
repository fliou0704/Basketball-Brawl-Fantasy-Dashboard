// Focused Team Summary checks against a freshly generated canonical export.
const {chromium}=require('playwright-core');
const fs=require('node:fs/promises');
const path=require('node:path');
const assert=require('node:assert/strict');
(async()=>{
  const root=process.env.BRAWL_EXPORT;
  assert.ok(root,'Set BRAWL_EXPORT to the generated export directory');
  const base=process.env.BRAWL_URL||'http://127.0.0.1:5173/Basketball-Brawl-Fantasy-Dashboard/';
  const payload=JSON.parse(await fs.readFile(path.join(root,'team-stats/16.json'),'utf8'));
  const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
  try {
    for(const width of [1280,390,320]) {
      const page=await browser.newPage({viewport:{width,height:1000}}),errors=[];
      page.on('pageerror',error=>errors.push(String(error)));
      await page.route('**/data/**',async route=>{
        const relative=decodeURIComponent(new URL(route.request().url()).pathname.split('/data/')[1]);
        const file=path.resolve(root,relative);
        if(!file.startsWith(root+'/'))return route.abort();
        try {await route.fulfill({body:await fs.readFile(file),contentType:'application/json'});} catch {await route.continue();}
      });
      await page.goto(base+'#/teams/16');
      await page.getByRole('heading',{name:'Overview',exact:true}).waitFor();
      assert.match(await page.locator('.team-fp-start small').innerText(),/Partial season/i);
      await page.getByLabel('Season',{exact:true}).selectOption('Summary');
      await page.getByRole('heading',{name:'Franchise Career',exact:true}).waitFor();
      assert.equal(await page.getByRole('tab',{name:'Performance',exact:true}).getAttribute('aria-selected'),'true');
      assert.equal(await page.locator('.franchise-history tbody tr').count(),payload.franchise.history.length);
      assert.equal(await page.locator('.franchise-trend').count(),3);
      const career=page.locator('.franchise-career > div').filter({has:page.getByText('FP/Start',{exact:true})});
      assert.equal(await career.locator('dd').innerText(),payload.franchise.totals.fpPerStart==null?'Unavailable':Number(payload.franchise.totals.fpPerStart).toLocaleString(undefined,{maximumFractionDigits:2}));
      const efficiency=page.locator('.franchise-trend').filter({has:page.getByRole('heading',{name:'Fantasy Points per Start',exact:true})});
      assert.equal(await efficiency.locator('circle').count(),payload.franchise.history.filter(row=>row.fpPerStart!=null).length);
      for(const row of payload.franchise.history) {
        const rendered=page.locator('.franchise-history tbody tr').filter({has:page.getByRole('button',{name:String(row.year),exact:true})});
        assert.ok((await rendered.innerText()).includes(row.team.teamName));
        assert.ok((await rendered.innerText()).includes(row.fpPerStart==null?'Unavailable':Number(row.fpPerStart).toLocaleString(undefined,{maximumFractionDigits:2})));
        assert.equal(await rendered.locator('img').getAttribute('src'),base.startsWith('http')?'/Basketball-Brawl-Fantasy-Dashboard/'+row.team.logo:row.team.logo);
      }
      const checkWidth=async()=>assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth)<=width,'no page overflow');
      await checkWidth();
      assert.ok(await page.locator('.franchise-historical-team').evaluateAll(nodes=>nodes.every(node=>node.getBoundingClientRect().right<=node.closest('td').getBoundingClientRect().right)),'historical identity stays inside its column');
      await page.locator('.franchise-trend circle').first().focus();
      assert.match(await page.locator('.franchise-hover').first().innerText(),/20\d\d:/);
      await page.screenshot({path:`/private/tmp/franchise-performance-${width}.png`,fullPage:true});
      await page.getByRole('tab',{name:'Achievements',exact:true}).click();
      await page.getByRole('heading',{name:'Notable Achievements',exact:true}).waitFor();
      await checkWidth();
      await page.getByRole('tab',{name:'All-Time Roster',exact:true}).click();
      await page.getByRole('heading',{name:'All-Time Roster',exact:true}).waitFor();
      assert.ok(await page.locator('.summary-roster tbody tr').count()>0);
      await checkWidth();
      await page.getByRole('tab',{name:'Performance',exact:true}).click();
      const historical=payload.franchise.history.find(row=>row.complete);
      await page.getByRole('button',{name:String(historical.year),exact:true}).click();
      await page.getByRole('heading',{name:'Overview',exact:true}).waitFor();
      assert.equal(await page.getByLabel('Season',{exact:true}).inputValue(),String(historical.year));
      for(const name of ['Category Rankings','Weekly Performance','Physicals','Roster'])await page.getByRole('tab',{name,exact:true}).click();
      for(const year of [2023,2025,2026]) {
        await page.getByLabel('Season',{exact:true}).selectOption(String(year));
        const metric=payload.seasons[String(year)].performance.season.fpPerStart;
        assert.equal(await page.locator('.team-fp-start strong').innerText(),metric==null?'Unavailable':Number(metric).toFixed(2));
      }
      assert.deepEqual(errors,[]);
      console.log('PASS',width,'Summary tabs, history/assets, chart interaction, season selection, existing season tabs, overflow');
      await page.close();
    }
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
