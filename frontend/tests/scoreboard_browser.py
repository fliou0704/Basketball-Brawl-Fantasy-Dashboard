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
 for width in (1280,390,320):
  page.set_viewport_size({'width':width,'height':1000})
  for week,dates in ((11,'2025-12-29 – 2026-01-04'),(17,'2026-02-09 – 2026-02-22'),(21,'2026-03-16 – 2026-03-22')):
   page.goto(base+f'#/scoreboard?season=2026&week={week}')
   page.get_by_text('Observed dates: '+dates,exact=True).wait_for()
   assert page.evaluate('document.documentElement.scrollWidth')<=width
  print('PASS observed history',width,'cross-year, extended, playoffs')
 fixture=page.request.get(base+'data/scoreboard.json').json()
 fixture['updatedAt']='2026-10-24T12:34:56Z'
 weeks=next(s for s in fixture['seasons'] if s['season']==2027)['weeks']
 weeks[0].update(start='2026-10-20',end='2026-10-25',calendarPartial=False)
 weeks[1].update(start='2026-10-26',end='2026-11-08',calendarPartial=False)
 page.route('**/data/scoreboard.json',lambda route:route.fulfill(json=fixture))
 for width in (1280,390,320):
  page.set_viewport_size({'width':width,'height':1000})
  page.goto(base+'#/scoreboard?season=2027&week=1')
  page.reload()
  page.get_by_text('Last updated:',exact=False).wait_for()
  assert page.locator('.scoreboard-context time').get_attribute('datetime')==fixture['updatedAt']
  assert '10/24/26 08:34:56 AM ET' in page.locator('.scoreboard-context').inner_text()
  assert '2026-10-20 – 2026-10-25' in page.locator('.scoreboard-context').inner_text()
  assert 'Fantasy points shown are actual scores' not in page.locator('main').inner_text()
  assert page.evaluate('document.documentElement.scrollWidth')<=width
  page.screenshot(path=f'/tmp/scoreboard-polish-{width}.png',full_page=True)
  page.get_by_label('Next week',exact=True).click()
  page.get_by_role('heading',name='Week 2',exact=True).wait_for()
  assert '2026-10-26 – 2026-11-08' in page.locator('.scoreboard-context').inner_text()
  assert 'Last updated' not in page.locator('main').inner_text()
  page.goto(base+'#/scoreboard?season=2026&week=23')
  page.get_by_role('heading',name='Week 23 · Playoffs',exact=True).wait_for()
  assert 'Last updated' not in page.locator('main').inner_text()
  print('PASS polish',width,'recorded timestamp only in progress, scheduled dates, disclaimer removed')
 future=next(s for s in fixture['seasons'] if s['season']==2027)['weeks'][1]
 future['matchups']=[]
 page.unroute('**/data/scoreboard.json')
 future.update(start=None,end=None)
 page.route('**/data/scoreboard.json',lambda route:route.fulfill(json=fixture))
 page.goto(base+'#/scoreboard?season=2027&week=2')
 page.reload()
 page.get_by_text('Matchup assignments are unavailable or have not been published for this week.').wait_for()
 assert page.locator('.match-team').count()==0
 assert 'Schedule dates unavailable.' in page.locator('.scoreboard-context').inner_text()
 assert not errors,errors
 browser.close()
