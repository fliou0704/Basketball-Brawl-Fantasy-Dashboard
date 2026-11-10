// Real HTTP smoke checks for the root preview and unchanged GitHub Pages base.
const {chromium}=require(process.env.PLAYWRIGHT_CORE_PATH||'playwright-core');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
 const baselineOverflow=new Map();
 try{
  for(const [base,preview]of [[process.env.PRODUCTION_PREVIEW_URL||'http://127.0.0.1:4179/Basketball-Brawl-Fantasy-Dashboard/',false],[process.env.PREVIEW_URL||'http://127.0.0.1:4178/',true]]){
   for(const width of [320,390,1280]){
    const p=await browser.newPage({viewport:{width,height:900}}),errors=[],bad=[],methods=[];
    p.on('pageerror',e=>errors.push(e.message));p.on('request',r=>methods.push(r.method()));
    p.on('response',r=>{if(r.url().startsWith(base)&&r.status()>=400)bad.push([new URL(r.url()).pathname,r.status()]);});
    for(const route of ['', '#/standings','#/players','#/top-150','#/teams/1','#/h2h/historical','#/record-book','#/scoreboard']){
     await p.goto(base+route,{waitUntil:'domcontentloaded'});await p.locator('main').waitFor();
     if(route==='#/top-150')await p.locator('.top150-table tbody tr').first().waitFor();
     await p.waitForTimeout(500);
     assert.equal(await p.locator('.preview-label').count(),preview?1:0);
     assert.equal(await p.getByRole('alert').count(),0);
     const scrollWidth=await p.evaluate(()=>document.documentElement.scrollWidth);
     if(width===320&&route==='#/teams/1'){if(!preview){baselineOverflow.set(route,scrollWidth);if(scrollWidth>width)console.log('Existing production overflow:',route,width,scrollWidth);}else assert.equal(scrollWidth,baselineOverflow.get(route),'Preview must not worsen existing narrow Team Overview overflow');}
     else assert.ok(scrollWidth<=width,'Page overflow: '+base+' '+width+' '+route);
    }
    const links=await p.locator('.brand').getAttribute('href');assert.equal(links,new URL(base).pathname);
    if(width<720){await p.getByRole('button',{name:'Open menu'}).click();assert.equal(await p.getByRole('button',{name:'Close menu'}).count(),1);}
    assert.deepEqual(errors,[]);assert.deepEqual(bad,[]);assert.ok(methods.every(m=>m==='GET'||m==='HEAD'));
    if(preview){const meta=await p.evaluate(async base=>(await fetch(base+'data/preview-build.json')).json(),base);assert.match(meta.canonicalCommit,/^[a-f0-9]{40}$/);assert.equal(meta.preview,true);}
    console.log(JSON.stringify({base,width,preview,routes:8,requestsReadOnly:true,assetsAndData:true}));
    if(width===390)await p.screenshot({path:'/private/tmp/cloudflare-'+(preview?'preview':'production')+'-390.png'});
    await p.close();
   }
  }
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
