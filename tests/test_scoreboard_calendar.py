"""Full ESPN schedule boundaries and validated snapshot time; no live requests."""
import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from nearLiveUpdater import current_calendar
from scoreboardCalendar import scheduled_weeks, dated_snapshot


class ScoreboardCalendarTests(unittest.TestCase):
    def test_real_weekly_settings_are_never_daily_boundaries(self):
        import json
        from pathlib import Path
        raw = json.loads((Path(__file__).parent / 'fixtures/scoreboard_calendar.json').read_text())
        self.assertEqual(raw['observedWeek1Periods'], [1,2,3,4,5,6])
        self.assertEqual(raw['scheduleSettings']['matchupPeriods']['1'], [1])
        self.assertEqual(scheduled_weeks(raw['scheduleSettings'], '2026-10-19', 1, 167), [])

    def test_even_plausible_arrays_without_verified_daily_semantics_are_rejected(self):
        for periods in (None, {}, {'1':[1]}, {'1':list(range(1,8)), '2':list(range(8,22))}):
            self.assertEqual(scheduled_weeks({'matchupPeriods':periods}, '2026-10-19', 1, 167), [])

    def test_current_calendar_keeps_observations_separate_without_new_requests(self):
        raw = {'status': {'firstScoringPeriod': 1}, 'teams': [],
               'settings': {'scheduleSettings': {'matchupPeriodCount':20, 'playoffTeamCount':6,
                                                 'periodTypeId':2, 'matchupPeriods':{'1':[1], '2':[2]}},
                            'rosterSettings': {'lineupSlotCounts': {}}, 'scoringSettings': {'scoringItems': []}},
               'schedule': [{'id':1,'matchupPeriodId':1,'home':{'teamId':1,'pointsByScoringPeriod':{str(p):0 for p in range(1,7)}}}]}
        calls = []
        def fetch(**kwargs):
            calls.append(kwargs)
            return raw
        league = SimpleNamespace(year=2027, scoringPeriodId=6, finalScoringPeriod=167, currentMatchupPeriod=1,
                                 teams=[],espn_request=SimpleNamespace(league_get=fetch))
        daily = pd.DataFrame([{'Year':2027,'Date':'2026-10-20','Scoring Period':1}])
        calendar = current_calendar(league, daily, {'seasons':[]})
        self.assertEqual(len(calls), 1)
        self.assertEqual((calendar['weeks'][0]['firstPeriod'], calendar['weeks'][0]['lastPeriod']), (1,6))
        self.assertEqual(calendar['scheduledWeeks'], [])

    def test_update_time_tracks_validated_data_and_survives_unchanged_refresh(self):
        snapshot, calendar = {'season':2027,'week':1}, {'matchups':[]}
        first = dated_snapshot(snapshot, calendar, None, None, '2026-10-24T12:00:00Z')
        unchanged = dated_snapshot(snapshot, calendar, first, copy.deepcopy(calendar), '2026-10-24T15:00:00Z')
        self.assertEqual(unchanged['updatedAt'], first['updatedAt'])
        changed = dated_snapshot(snapshot, {'matchups':[{'points':10}]}, first, calendar, '2026-10-24T18:00:00Z')
        self.assertEqual(changed['updatedAt'], '2026-10-24T18:00:00Z')


if __name__ == '__main__':
    unittest.main()
