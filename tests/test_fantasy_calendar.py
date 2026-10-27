"""Public ESPN fixture, persisted throttling, and immutable scoring history."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from espnFantasyCalendar import (CalendarError, context, discover, normalize,
                                 refresh, validate, verified, week_ranges)
from nearLiveUpdater import atomic_json
from scoreboardCalendar import dated_snapshot

FIXTURE = json.loads((Path(__file__).parent / 'fixtures/fantasy_calendar_2027.json').read_text())


class CalendarTests(unittest.TestCase):
    def setUp(self):
        self.constants = deepcopy(FIXTURE['constants'])
        self.ctx = context(FIXTURE['league'])
        self.now = datetime(2026, 10, 27, 15, tzinfo=timezone.utc)
        self.calls = []

    def fetch(self, season):
        self.calls.append(season)
        return self.constants, 'https://fantasy.espn.com/basketball/league/scoreboard'

    def refresh(self, old=None, **kwargs):
        return refresh(old, self.ctx, now=kwargs.pop('now', self.now), fetch=self.fetch, log=lambda _: None, **kwargs)

    def test_real_calendar_full_extended_and_playoffs(self):
        value = self.refresh()
        self.assertEqual(len(value['days']), 167)
        weeks = {w['week']: w for w in week_ranges(value)}
        self.assertEqual(len(weeks), 23)
        for w, a, z in [(2, '2026-10-26', '2026-11-01'), (18, '2027-02-15', '2027-02-28'),
                        (21, '2027-03-15', '2027-03-21'), (23, '2027-03-29', '2027-04-04')]:
            self.assertEqual((weeks[w]['start'], weeks[w]['end']), (a, z))
        self.assertEqual(weeks[1]['start'], '2026-10-20')  # not offseason startDate

    def test_schema_duplicates_missing_dates_and_boundaries_rejected(self):
        mutations = [lambda c: c.pop('segments'), lambda c: c.update(seasonConfig=2026),
                     lambda c: c['scoringPeriods'].append(c['scoringPeriods'][1]),
                     lambda c: c['scoringPeriods'].pop(7),
                     lambda c: c['scoringPeriods'][7].update(endDate='bad'),
                     lambda c: c['scoringPeriods'][7].update(endDate=0),
                     lambda c: c['segments'][0]['periodTypes'][0]['periods'][1].update(scoringPeriodStart=6)]
        for change in mutations:
            with self.subTest(change=change):
                c = deepcopy(self.constants); change(c)
                with self.assertRaises(CalendarError): normalize(c, self.ctx)
        good = normalize(self.constants, self.ctx)
        for rows in ([dict(r, date='2026-02-30') if r['period']==7 else r for r in good['days']], list(reversed(good['days']))):
            with self.assertRaises(CalendarError): validate(dict(good, days=rows))

    def test_multiple_base_periods_use_real_boundaries_not_week_arithmetic(self):
        ctx = deepcopy(self.ctx)
        ctx['matchupPeriods'] = {str(w): ([18,19] if w==18 else [w] if w<18 else [w+1]) for w in range(1,23)}
        ctx['regularWeeks'] = 19
        value = normalize(self.constants,ctx)
        extended = next(w for w in week_ranges(value) if w['week']==18)
        self.assertEqual(extended['lastPeriod']-extended['firstPeriod']+1,21)
        self.assertEqual(len(value['days']),167)

    def test_host_zones_and_dst_labels(self):
        before = os.environ.get('TZ')
        try:
            for zone in ['UTC', 'America/New_York', 'America/Los_Angeles', 'Asia/Tokyo']:
                os.environ['TZ'] = zone; time.tzset()
                rows = normalize(self.constants, self.ctx)['days']
                self.assertEqual(rows[11]['date'], '2026-10-31')
                self.assertEqual(rows[145]['date'], '2027-03-14')
        finally:
            if before is None: os.environ.pop('TZ', None)
            else: os.environ['TZ'] = before
            time.tzset()

    def test_persisted_success_skip_stale_and_force(self):
        initial = self.refresh()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'seasonMetadata.json'
            atomic_json({'seasons': [{'season':2027, 'fantasyCalendar':initial}]}, path)
            restored = json.loads(path.read_text())['seasons'][0]['fantasyCalendar']
            for hours in [3, 23]:
                self.assertEqual(self.refresh(restored, now=self.now+timedelta(hours=hours)), initial)
            self.assertEqual(self.calls, [2027])
            stale = self.refresh(restored, now=self.now+timedelta(hours=24))
            self.assertNotEqual(stale['verifiedAt'], initial['verifiedAt'])
            self.refresh(stale, force=True, now=self.now+timedelta(hours=25))
            self.assertEqual(self.calls, [2027]*3)
        other_season = deepcopy(initial)
        other_season['context']['season'] = 2026
        self.refresh(other_season)
        self.assertEqual(self.calls, [2027]*4)

    def test_network_and_validation_failure_keep_success_and_persistent_cooldown(self):
        old = self.refresh()
        def fail(_): raise CalendarError('network unavailable')
        now = self.now+timedelta(days=1)
        failed = refresh(old, self.ctx, now=now, fetch=fail, log=lambda _:None)
        self.assertEqual(failed['verifiedAt'], old['verifiedAt'])
        self.assertEqual(failed['days'], old['days'])
        self.assertIn('lastError', failed)
        restored = json.loads(json.dumps(failed))
        self.refresh(restored, now=now+timedelta(hours=3))
        self.assertEqual(self.calls, [2027])
        self.constants.pop('segments')
        invalid = self.refresh(old, now=now)
        self.assertEqual(invalid['days'], old['days'])
        self.assertEqual(invalid['verifiedAt'], old['verifiedAt'])

    def test_failed_initialization_does_not_repeat_every_run_and_new_season_initializes(self):
        self.constants.pop('segments')
        failed = self.refresh()
        self.assertNotIn('verifiedAt', failed)
        self.refresh(json.loads(json.dumps(failed)), now=self.now+timedelta(hours=3))
        self.assertEqual(self.calls, [2027])
        # Previous season has a separate cache in seasonMetadata; no global clock.
        self.constants = deepcopy(FIXTURE['constants'])
        new = self.refresh(None)
        self.assertEqual(self.calls, [2027,2027])
        self.assertIsNotNone(verified({'season':2027,'fantasyCalendar':new,'fantasyCalendarContext':self.ctx}))
        changed = dict(self.ctx, regularWeeks=19)
        self.assertIsNone(verified({'season':2027,'fantasyCalendar':new,'fantasyCalendarContext':changed}))

    def test_future_changes_accepted_historical_conflicts_rejected(self):
        old = self.refresh()
        periods = self.constants['segments'][0]['periodTypes'][0]['periods']
        periods[17]['scoringPeriodEnd'] = 133
        periods[18]['scoringPeriodStart'] = 134
        updated = self.refresh(old, force=True, through=8)
        self.assertNotEqual(old['days'], updated['days'])
        self.assertEqual(updated['days'][132]['week'], 18)
        rejected = self.refresh(old, force=True, through=133)
        self.assertEqual(rejected['days'], old['days'])
        self.assertIn('history', rejected['lastError'])

    def test_observed_dates_and_membership_are_never_rewritten(self):
        old = self.refresh()
        for kwargs in [{'daily':[{'Year':2027,'Scoring Period':7,'Date':'2026-10-27'}]},
                       {'mapping':[{'Year':2027,'Scoring Period':7,'Week':1}]}]:
            result = self.refresh(old, force=True, **kwargs)
            self.assertEqual(result['days'], old['days'])
            self.assertIn('observed', result['lastError'])

    def test_calendar_checks_do_not_redate_scoring_snapshot(self):
        snap = {'season':2027,'updatedAt':'2026-10-26T00:00:00Z'}
        result = dated_snapshot({'season':2027}, {'weeks':[],'fantasyCalendar':self.refresh()}, snap,
                                {'weeks':[]}, '2026-10-27T00:00:00Z')
        self.assertEqual(result['updatedAt'], snap['updatedAt'])

    def test_bootstrap_and_archive_parsing_without_remote_execution(self):
        html = '__NEXT_DATA__ = '+json.dumps({'props':{'pageProps':{'page':{'config':{'constants':self.constants}}}}})
        with patch('espnFantasyCalendar._get', return_value=html) as get:
            self.assertEqual(discover(2027)[0], self.constants)
            self.assertEqual(get.call_count, 1)
        html += '<script src="https://cdn1.espn.net/kona/v/_next/static/commons/main-abc.js"></script>'
        loader = '1:"chunks/modules_api_lm_seasons_fba_2026_abc";1:"12345678901234567890"'
        chunk = 'e.exports=[{endDate:2,id:1,preSeason:false,postSeason:false,startDate:1}];e.exports=[{id:0,periodTypes:[]}]'
        with patch('espnFantasyCalendar._get', side_effect=[html,loader,chunk]) as get:
            constants, url = discover(2026)
            self.assertEqual(constants['seasonConfig'],2026)
            self.assertIn('/_next/webpack/',url)
            self.assertEqual(get.call_count,3)


if __name__ == '__main__': unittest.main()
