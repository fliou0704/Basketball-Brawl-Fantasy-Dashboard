"""Regression checks for bounded corrections, independent of ESPN/network."""
import unittest
from datetime import datetime
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from dataUpdateSafety import DataValidationError, PLAYER_DAILY_KEY, validate_player_daily_data
from nearLiveSafety import refresh_start, replace_partitions, changes
from nearLiveUpdater import live_rosters
from playerDailyDataUpdater import fetch_daily_rows
from dataUpdateSafety import LEAGUE_KEY, validate_league_data
from tests.test_production_update_safety import league_season
from tests.test_production_update_safety import player_week
from tests.test_activity_data_updater import activity_row
from tests.test_production_update_safety import daily_period


class BoundedReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.old = pd.concat([daily_period(2026, p) for p in range(1, 11)], ignore_index=True)
        self.authorized = {(2026, p) for p in range(4, 12)}
        self.fetched = pd.concat([daily_period(2026, p) for p in range(4, 12)], ignore_index=True)

    def merge(self, rows):
        return replace_partitions(self.old, rows, self.authorized, 'Scoring Period',
                                  PLAYER_DAILY_KEY, validate_player_daily_data)

    def test_window_and_outage_catchup(self):
        self.assertEqual(refresh_start(10, 11), 5)
        self.assertEqual(refresh_start(2, 20), 3)
        self.assertEqual(refresh_start(0, 1), 1)
        self.assertEqual(refresh_start(175, 175), 169)

    def test_corrections_insertions_deletions_and_immutable_history(self):
        self.fetched.loc[0, 'FPTS'] += 5
        self.fetched = self.fetched.drop(index=1)
        candidate = self.merge(self.fetched)
        pd.testing.assert_frame_equal(candidate.iloc[:6], self.old.iloc[:6])
        self.assertEqual(changes(self.old, candidate, PLAYER_DAILY_KEY),
                         {'inserted': 2, 'removed': 1, 'corrected': 1})
        self.assertFalse(candidate.duplicated(PLAYER_DAILY_KEY).any())

    def test_idempotence_and_historical_eligibility(self):
        self.fetched.loc[0, 'Position'] = 'C'
        candidate = self.merge(self.fetched)
        self.assertEqual(candidate.loc[candidate['Scoring Period'] == 4, 'Position'].iloc[0], 'PG')
        repeated = replace_partitions(candidate, self.fetched, self.authorized, 'Scoring Period',
                                      PLAYER_DAILY_KEY, validate_player_daily_data)
        pd.testing.assert_frame_equal(candidate, repeated)

    def test_duplicate_and_outside_window_rejected(self):
        with self.assertRaises(DataValidationError):
            self.merge(pd.concat([self.fetched, self.fetched.iloc[:1]]))
        with self.assertRaises(DataValidationError):
            self.merge(pd.concat([self.fetched, daily_period(2025, 1)]))

    def test_rollover_terminal_validation(self):
        candidate = self.merge(self.fetched)
        candidate = pd.concat([candidate, daily_period(2027, 1)])
        validate_player_daily_data(candidate, {2026: 11})
        with self.assertRaises(DataValidationError):
            validate_player_daily_data(candidate, {2026: 12})

    def test_no_change_keeps_original_order(self):
        fetched = self.old[self.old['Scoring Period'] >= 4].iloc[::-1]
        candidate = self.merge(fetched)
        pd.testing.assert_frame_equal(candidate, self.old)

    def test_current_roster_uses_official_team_records(self):
        team = SimpleNamespace(team_id=1, team_name='One', team_abbrev='ONE', owners=[{'firstName': 'Owner'}],
            wins=0, losses=0, standing=1, roster=[SimpleNamespace(playerId=101, name='Alpha', eligibleSlots=['PG', 'UT'])])
        league = SimpleNamespace(year=2027, currentMatchupPeriod=1, scoringPeriodId=1, finalScoringPeriod=167,
            teams=[team], _brawl_raw={'teams': [{'id': 1, 'record': {'overall': {'pointsFor': 0, 'pointsAgainst': 0}}}]})
        snapshot = live_rosters(league)
        self.assertEqual(snapshot['teams'][0]['pointsFor'], 0)
        self.assertEqual(snapshot['teams'][0]['roster'][0]['playerId'], 101)

    def test_incomplete_daily_response_is_rejected_before_partition_replacement(self):
        league = SimpleNamespace(teams=[SimpleNamespace(team_id=1)], box_scores=lambda **kwargs: [])
        with self.assertRaisesRegex(DataValidationError, 'incomplete ESPN lineup'):
            fetch_daily_rows(league, 2027, 1, 1, self.old.columns.tolist())

    def test_playoff_rank_does_not_drift_without_an_official_result_change(self):
        old = league_season(2026, 2)
        old.loc[old.Week == 2, 'Type'] = 'Consolation'
        fetched = old[old.Week == 2].copy()
        fetched['Rank'] = 3 - fetched['Rank']
        candidate = replace_partitions(old, fetched, {(2026, 2)}, 'Week', LEAGUE_KEY, validate_league_data)
        pd.testing.assert_frame_equal(candidate, old)

    def test_later_validation_failure_does_not_promote_earlier_daily_candidate(self):
        from nearLiveUpdater import run
        now = datetime.now()
        active_year = now.year + (now.month >= 7)
        prior_year = active_year - 1
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            daily = pd.concat([daily_period(prior_year, p) for p in range(1, 11)], ignore_index=True)
            frames = {'playerDailyData.csv': daily,
                      'basketballBrawlLeagueData.csv': league_season(prior_year, 2),
                      'playerMatchupData.csv': player_week(prior_year, 1),
                      'activityData.csv': pd.DataFrame([activity_row(0, prior_year)])}
            for name, frame in frames.items():
                frame.to_csv(root / name, index=False)
            original = {name: (root / name).read_bytes() for name in frames}
            def factory(league_id, year, **kwargs):
                return SimpleNamespace(year=year, scoringPeriodId=1 if year == active_year else 12,
                    finalScoringPeriod=10, currentMatchupPeriod=1 if year == active_year else 2,
                    matchup_ids={1: [str(p) for p in range(1, 11)]})
            def fetch(league, year, first, last, columns):
                return pd.concat([daily_period(year, p) for p in range(first, last + 1)], ignore_index=True)
            with patch('nearLiveUpdater.require_espn_credentials', return_value=('fixture', 'fixture')), \
                 patch('nearLiveUpdater.draft_is_complete', return_value=(True, 1)), \
                 patch('nearLiveUpdater.LeagueCache', return_value=factory), \
                 patch('nearLiveUpdater.fetch_daily_rows', side_effect=fetch), \
                 patch('nearLiveUpdater.update_league_data', side_effect=DataValidationError('fixture failure')):
                with self.assertRaises(DataValidationError):
                    run(root, write=True)
            for name in frames:
                self.assertEqual((root / name).read_bytes(), original[name])
