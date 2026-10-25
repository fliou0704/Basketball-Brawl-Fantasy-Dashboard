"""Real archived calendar and allowlisted live ESPN shape regressions."""
import csv
import json
from pathlib import Path
import unittest
from generate_scoreboard import project
from build_homepage import logo_config

ROOT = Path(__file__).resolve().parents[2]

class RealCalendarTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads((ROOT / 'tests/fixtures/scoreboard_calendar.json').read_text())
        self.calendars = json.loads((ROOT / 'data/seasonMetadata.json').read_text())['seasons']
        self.current = json.loads((ROOT / 'data/currentLeague.json').read_text())
        self.mapping = list(csv.DictReader((ROOT / 'data/scoringPeriodMatchupMap.csv').read_text().splitlines()))
        self.league = list(csv.DictReader((ROOT / 'data/basketballBrawlLeagueData.csv').read_text().splitlines()))

    def build(self):
        return project(self.current, self.calendars, self.mapping, self.league, logo_config())

    def test_all_93_historical_ranges_restored_without_schedule_data(self):
        result = self.build()
        historical = [w for s in result['seasons'] if s['season'] < 2027 for w in s['weeks'] if w['start'] and w['end']]
        self.assertEqual(len(historical), 93)
        for season in result['seasons']:
            saved = next(c for c in self.calendars if c['season'] == season['season'])
            for week in season['weeks']:
                if week['start']:
                    old = next(w for w in saved['weeks'] if w['week'] == week['week'])
                    self.assertEqual((week['start'], week['end']), (old['start'], old['end']))
                    self.assertEqual(week['dateRangeKind'], 'observed')

    def test_extended_playoff_and_cross_year_are_retained(self):
        season = next(s for s in self.build()['seasons'] if s['season'] == 2026)
        for number, first, last, start, end in (
            (1,1,6,'2025-10-21','2025-10-26'),
            (17,112,125,'2026-02-09','2026-02-22'),
            (21,147,153,'2026-03-16','2026-03-22'),
            (11,70,76,'2025-12-29','2026-01-04')):
            week = next(w for w in season['weeks'] if w['week'] == number)
            self.assertEqual((week['firstPeriod'],week['lastPeriod'],week['start'],week['end']), (first,last,start,end))
        self.assertEqual(next(w for w in season['weeks'] if w['week'] == 21)['phase'], 'playoffs')

    def test_live_week_one_observation_cannot_become_scheduled_end(self):
        self.current.update(scoringPeriod=6, week=1)
        self.mapping += [{'Year':'2027','Scoring Period':str(p),'Week':'1'} for p in range(2,7)]
        calendar = next(s for s in self.calendars if s['season']==2027)
        calendar['weeks'][0].update(lastPeriod=6,end='2026-10-25')
        calendar['scheduledWeeks'] = [{'week':int(w), 'firstPeriod':p[0], 'lastPeriod':p[-1],
            'start':'2026-10-20','end':'2026-10-20'} for w,p in self.fixture['scheduleSettings']['matchupPeriods'].items()]
        season = next(s for s in self.build()['seasons'] if s['season']==2027)
        for week in season['weeks']:
            self.assertEqual(week['dateRangeKind'], 'unavailable')
            self.assertIsNone(week['start'])
            self.assertIsNone(week['end'])

    def test_missing_or_inconsistent_historical_endpoint_is_not_invented(self):
        calendar = next(c for c in self.calendars if c['season']==2026)
        calendar['weeks'][0].pop('end')
        calendar['weeks'][1]['lastPeriod'] = calendar['weeks'][1]['firstPeriod']
        season = next(s for s in self.build()['seasons'] if s['season']==2026)
        for week in season['weeks'][:2]:
            self.assertIsNone(week['end'])
            self.assertEqual(week['dateRangeKind'], 'unavailable')

if __name__ == '__main__':
    unittest.main()
