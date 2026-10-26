"""Deterministic Home/Scoreboard lifecycle and responsive checks against Vite."""
from copy import deepcopy
from pathlib import Path
import json
import os
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright

base = os.environ.get('BRAWL_URL', 'http://localhost:5173/Basketball-Brawl-Fantasy-Dashboard/')
data = Path(os.environ.get('BRAWL_DATA_DIR', Path(__file__).resolve().parents[1] / 'public/data'))
current = json.loads((data / 'home-current.json').read_text())
current.update(season=2027, week=2, asOfDate='2026-10-26', scoringPeriod=7,
               scoringStatus='zero', players=[])
current['state'].update(season=2027, week=2, weeklyWeek=1, scoringPeriod=7,
                        weekScoringPeriods=[7, 8, 9, 10], phase='regular',
                        dailyDate='2026-10-25')
for match in current['matchups']:
    match['scoreDisplay'] = ['0', '0']
player = deepcopy(json.loads((data / '2027/daily-recap.json').read_text())['data']['2026-10-25']['players'][0])
player.update(date='2026-10-26', scoringPeriod=7)
executables = ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/usr/bin/chromium']
executable = os.environ.get('CHROMIUM_PATH') or next((p for p in executables if Path(p).exists()), None)

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=executable, headless=True)
    page = browser.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.route('**/data/home-current.json?*', lambda route: route.fulfill(json=current))

    def visit():
        page.goto(base + '?date=2026-10-26')
        page.get_by_role('heading', name='2027 Week 2 Scoreboard', exact=True).wait_for()
        assert page.evaluate('document.documentElement.scrollWidth') <= page.viewport_size['width']
        return page.locator('main section > .section-title h2').all_text_contents()

    def verify_weekly():
        recap = page.locator('.weekly-recap')
        for selector in ('.content-card', '.lineup-player'):
            boxes = [item.bounding_box() for item in recap.locator(selector).all()]
            assert boxes
            for previous, following in zip(boxes, boxes[1:]):
                assert following['y'] >= previous['y'] + previous['height'] - 1, boxes
                assert abs(following['x'] - previous['x']) < 1, boxes
                assert abs(following['width'] - previous['width']) < 1, boxes
        assert recap.locator('.lineup-fantasy-team img').count() == recap.locator('.lineup-player').count()
        return recap.locator('.weekly-player-stats').all_text_contents()

    for width in (1280, 390, 320):
        page.set_viewport_size({'width': width, 'height': 1000})
        current.update(scoringStatus='zero', players=[])
        for period, visible in [(7, True), (8, True), (9, False)]:
            current['scoringPeriod'] = current['state']['scoringPeriod'] = period
            titles = visit()
            expected = (['Week 1 Recap'] if visible else []) + [
                'October 25, 2026 Recap', '2027 Week 2 Scoreboard', 'Standings']
            assert titles == expected, titles
            assert not page.get_by_role('heading', name='Best Week 2 Performances').count()
            if visible:
                home_stats = verify_weekly()
        current['scoringPeriod'] = current['state']['scoringPeriod'] = 7
        current.update(scoringStatus='started', players=[player])
        current['matchups'][0]['scoreDisplay'][0] = '12'
        assert visit() == ['2027 Week 2 Scoreboard', 'Best Week 2 Performances',
                           'October 25, 2026 Recap', 'Week 1 Recap', 'Standings']
        current['state']['scoringPeriod'] = current['scoringPeriod'] = 9
        assert 'Week 1 Recap' not in visit()
        current['state'].update(scoringPeriod=None)
        current.update(scoringStatus='unavailable', players=[])
        assert visit() == ['2027 Week 2 Scoreboard', 'October 25, 2026 Recap', 'Standings']
        page.screenshot(path=f'/tmp/recap-home-{width}.png', full_page=True)

        if width < 720:
            menu = page.get_by_role('button', name='Open menu', exact=True)
            menu.click()
            assert page.get_by_role('button', name='Close menu').get_attribute('aria-expanded') == 'true'
            page.get_by_role('button', name='Close menu').click()
            assert menu.get_attribute('aria-expanded') == 'false'
        else:
            assert page.locator('.menu-button').is_hidden()
            assert page.get_by_role('navigation', name='Main navigation').is_visible()
        page.goto(base + '#/scoreboard?season=2027&week=1')
        page.get_by_role('heading', name='Week 1 Recap', exact=True).wait_for()
        assert page.locator('.lineup-player').count() > 0
        assert verify_weekly() == home_stats
        assert page.evaluate('document.documentElement.scrollWidth') <= width
        page.goto(base + '#/scoreboard?season=2027&week=2')
        page.get_by_role('heading', name='Week 2', exact=True).wait_for()
        assert not page.locator('.weekly-recap').count()
        print('PASS', width, 'period window, zero/started/missing orders, headings, navigation, Scoreboard recaps, overflow')

    # A visitor clock advancing cannot age out the same published ESPN period.
    current['state']['scoringPeriod'] = current['scoringPeriod'] = 7
    current.update(scoringStatus='zero', players=[])
    page.clock.install(time=datetime(2026, 10, 26, 16, tzinfo=timezone.utc))
    page.goto(base)
    page.get_by_role('heading', name='Week 1 Recap', exact=True).wait_for()
    page.clock.set_system_time(datetime(2026, 10, 28, 4, tzinfo=timezone.utc))
    page.clock.fast_forward(60001)
    assert page.get_by_role('heading', name='Week 1 Recap', exact=True).count() == 1
    print('PASS stale snapshot retains published recap window despite clock rollover')
    assert not errors, errors
    browser.close()
