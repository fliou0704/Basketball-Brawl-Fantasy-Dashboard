"""Optional browser regression for the Stage 1 fixture; run against Vite."""
from playwright.sync_api import sync_playwright
import json, os
base=os.environ.get('BRAWL_URL','http://localhost:5173/Basketball-Brawl-Fantasy-Dashboard/')
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
 page=browser.new_page()
 errors=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 for width in (1280,720,390,320):
  page.set_viewport_size({'width':width,'height':1000})
  page.goto(base+'#/scoreboard')
  page.get_by_role('heading',name='Week 1',exact=True).wait_for()
  assert page.locator('.scoreboard-match').count()==5
  assert page.locator('.match-status.current').count()==5
  assert page.evaluate('document.documentElement.scrollWidth')<=width,(width,page.evaluate('document.documentElement.scrollWidth'))
  page.screenshot(path=f'/tmp/scoreboard-{width}.png',full_page=True)
  page.get_by_label('Next week',exact=True).click()
  page.get_by_role('heading',name='Week 2',exact=True).wait_for()
  assert page.locator('.match-status.future').count()==5
  assert page.locator('.match-team strong').all_text_contents()==['—']*10
  page.reload()
  page.get_by_role('heading',name='Week 2',exact=True).wait_for()
  page.get_by_role('button',name='Current week',exact=True).click()
  page.get_by_role('heading',name='Week 1',exact=True).wait_for()
  page.go_back()
  page.get_by_role('heading',name='Week 2',exact=True).wait_for()
  page.go_forward()
  page.get_by_role('heading',name='Week 1',exact=True).wait_for()
  page.get_by_label('Previous week',exact=True).click()
  page.get_by_role('heading',name='Week 23 · Playoffs',exact=True).wait_for()
  assert page.locator('.scoreboard-controls select').nth(0).input_value()=='2026'
  page.locator('.scoreboard-controls select').nth(1).select_option('21')
  assert page.locator('.match-status.bye').count()==2
  page.screenshot(path=f'/tmp/scoreboard-playoff-{width}.png',full_page=True)
  page.goto(base+'#/scoreboard?season=2027&week=999')
  page.get_by_text('This season or week is unavailable.',exact=False).wait_for()
  print('PASS',width,'default, future, refresh, back/forward, season transition, byes, unavailable, overflow')
 fixture=page.request.get(base+'data/scoreboard.json').json()
 future=next(s for s in fixture['seasons'] if s['season']==2027)['weeks'][1]
 future['matchups']=[]
 page.route('**/data/scoreboard.json',lambda route:route.fulfill(json=fixture))
 page.goto(base+'#/scoreboard?season=2027&week=2')
 page.reload()
 page.get_by_text('Matchup assignments are unavailable or have not been published for this week.').wait_for()
 assert page.locator('.match-team').count()==0
 assert not errors,errors
 browser.close()
