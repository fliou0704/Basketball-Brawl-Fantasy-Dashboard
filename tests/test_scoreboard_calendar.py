"""Full ESPN schedule boundaries and validated snapshot time; no live requests."""
import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from nearLiveUpdater import current_calendar
from scoreboardCalendar import scheduled_weeks, dated_snapshot


class ScoreboardCalendarTests(unittest.TestCase):
    def test_explicit_current_future_extended_and_playoff_periods(self):
        settings = {'matchupPeriods': {'1': list(range(1, 7)), '2': list(range(7, 14)),
                                       '3': list(range(14, 28)), '4': list(range(28, 42))}}
        weeks = scheduled_weeks(settings, '2026-12-20', 1, 41)
        self.assertEqual([(w['start'], w['end']) for w in weeks], [
            ('2026-12-21', '2026-12-26'), ('2026-12-27', '2027-01-02'),
            ('2027-01-03', '2027-01-16'), ('2027-01-17', '2027-01-30')])
        self.assertEqual(weeks[-1]['lastPeriod'], 41)

    def test_unpublished_invalid_and_overlapping_schedules_are_unavailable(self):
        for periods in (None, {}, [], {'1': []}, {'1': [1, 2], '2': [2, 3]},
                        {'1': [0]}, {'1': [5]}, {'1': [1.5]}, {'1': [True]}, {'1': ['bad']}):
            with self.subTest(periods=periods):
                self.assertEqual(scheduled_weeks({'matchupPeriods':periods}, '2026-10-19', 1, 4), [])

    def test_current_calendar_keeps_scheduled_dates_separate_without_new_requests(self):
        raw = {'status': {'firstScoringPeriod': 1}, 'teams': [],
               'settings': {'scheduleSettings': {'matchupPeriodCount': 1, 'playoffTeamCount': 2,
                                                 'matchupPeriods': {'1': [1,2,3,4,5,6], '2':[7,8,9,10]}},
                            'rosterSettings': {'lineupSlotCounts': {}}, 'scoringSettings': {'scoringItems': []}},
               'schedule': [{'id':1,'matchupPeriodId':1,'home':{'teamId':1,'pointsByScoringPeriod':{'1':5}}}]}
        calls = []
        def fetch(**kwargs):
            calls.append(kwargs)
            return raw
        league = SimpleNamespace(year=2027, scoringPeriodId=1, finalScoringPeriod=10, currentMatchupPeriod=1,
                                 teams=[],espn_request=SimpleNamespace(league_get=fetch))
        daily = pd.DataFrame([{'Year':2027,'Date':'2026-10-20','Scoring Period':1}])
        calendar = current_calendar(league, daily, {'seasons':[]})
        self.assertEqual(len(calls), 1)  # Same existing mSettings/mMatchupScore/mTeam call.
        self.assertEqual(calendar['weeks'][0]['end'], '2026-10-20')  # Observations unchanged.
        self.assertEqual(calendar['scheduledWeeks'][0]['end'], '2026-10-25')
        self.assertEqual(calendar['scheduledWeeks'][1]['start'], '2026-10-26')
        self.assertEqual(calendar['scheduledWeeks'][1]['end'], '2026-10-29')
        self.assertEqual(calendar['matchups'][0]['sides'][0]['pointsByPeriod'], {'1':5.0})

    def test_update_time_tracks_validated_data_and_survives_unchanged_refresh(self):
        snapshot, calendar = {'season':2027,'week':1}, {'matchups':[]}
        first = dated_snapshot(snapshot, calendar, None, None, '2026-10-24T12:00:00Z')
        unchanged = dated_snapshot(snapshot, calendar, first, copy.deepcopy(calendar), '2026-10-24T15:00:00Z')
        self.assertEqual(unchanged['updatedAt'], first['updatedAt'])
        changed = dated_snapshot(snapshot, {'matchups':[{'points':10}]}, first, calendar, '2026-10-24T18:00:00Z')
        self.assertEqual(changed['updatedAt'], '2026-10-24T18:00:00Z')


if __name__ == '__main__':
    unittest.main()
