"""Deterministic Home/Scoreboard lifecycle and responsive checks against Vite."""
from pathlib import Path
import json
import os
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright

base = os.environ.get('BRAWL_URL', 'http://localhost:5173/Basketball-Brawl-Fantasy-Dashboard/')
data = Path(__file__).resolve().parents[1] / 'public/data'
current = json.loads((data / 'home-current.json').read_text())
# Fixture days represent a verified boundary, independent of observed games.
current.update(asOfDate='2026-10-26')
current['state'].update(verifiedWeekStart='2026-10-26')
current['players'] = []
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/usr/bin/chromium', headless=True,
                                args=['--no-sandbox'])
    page = browser.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.route('**/data/home-current.json?*', lambda route: route.fulfill(json=current))
    for width in (1280, 390, 320):
        page.set_viewport_size({'width': width, 'height': 1000})
        for day, visible in [('2026-10-26', True), ('2026-10-27', True), ('2026-10-28', False)]:
            current['asOfDate'] = day
            page.goto(base + '?date=' + day)
            page.get_by_role('heading', name='Daily Recap', exact=True).wait_for()
            assert page.get_by_role('heading', name='Week 1 Recap', exact=True).count() == int(visible)
            assert not page.get_by_role('heading', name='Best Week 2 Performances').count()
            titles = page.locator('main section > .section-title h2').all_text_contents()
            assert titles[-1] == 'Standings', titles
            assert 'Around the League' not in page.locator('main').inner_text()
            assert 'Toughest Loss' not in page.locator('main').inner_text()
            assert page.evaluate('document.documentElement.scrollWidth') <= width
        current['asOfDate'] = '2026-10-26'
        current['state']['verifiedWeekStart'] = None
        page.goto(base + '?date=2026-10-26')
        page.get_by_role('heading', name='Daily Recap', exact=True).wait_for()
        assert not page.get_by_role('heading', name='Week 1 Recap', exact=True).count()
        current['state']['verifiedWeekStart'] = '2026-10-26'
        for season, week in [(2027, 1), (2026, 17), (2026, 21), (2023, 1)]:
            page.goto(base + f'#/scoreboard?season={season}&week={week}')
            page.get_by_role('heading', name=f'Week {week} Recap', exact=True).wait_for()
            assert page.locator('.lineup-player').count() > 0
            assert page.evaluate('document.documentElement.scrollWidth') <= width
            sections = page.locator('main section').all_text_contents()
            assert 'Recap' in sections[-1]
        page.goto(base + '#/scoreboard?season=2027&week=2')
        page.get_by_role('heading', name='Week 2', exact=True).wait_for()
        assert not page.locator('.weekly-recap').count()
        page.screenshot(path=f'/tmp/recap-scoreboard-{width}.png', full_page=True)
        print('PASS', width, 'Home window/fallback/order, empty leaders, historical/extended/playoff recaps')
    # First recorded game appears immediately, including a valid zero FPTS game.
    player = json.loads((data / '2027/daily-recap.json').read_text())['data']['2026-10-25']['players'][0]
    player.update(date='2026-10-26', scoringPeriod=8, pointsDisplay='0')
    current['players'] = [player]
    page.goto(base + '?date=2026-10-26')
    page.get_by_role('heading', name='Best Week 2 Performances', exact=True).wait_for()
    assert page.evaluate('document.documentElement.scrollWidth') <= 320
    # The open page ages out at New York midnight without new published data.
    current['players'] = []
    page.clock.install(time=datetime(2026, 10, 26, 16, tzinfo=timezone.utc))
    page.goto(base)
    page.get_by_role('heading', name='Week 1 Recap', exact=True).wait_for()
    page.clock.set_system_time(datetime(2026, 10, 28, 4, tzinfo=timezone.utc))
    page.clock.fast_forward(60001)
    page.get_by_role('heading', name='Week 1 Recap', exact=True).wait_for(state='hidden')
    print('PASS first zero-FPTS game, clock rollover without new player games')
    assert not errors, errors
    browser.close()
