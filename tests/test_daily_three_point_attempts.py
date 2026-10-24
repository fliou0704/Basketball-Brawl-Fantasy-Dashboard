"""Raw, unscored attempts must survive bounded refreshes without changing FPTS."""
from datetime import datetime, timezone
from types import SimpleNamespace
import unittest

import pandas as pd

from dataUpdateSafety import DataValidationError, PLAYER_DAILY_KEY, validate_player_daily_data
from nearLiveSafety import replace_partitions
from playerDailyDataUpdater import _record_for_player, fetch_daily_rows, with_raw_three_point_attempts
from tests.test_production_update_safety import daily_period


class ThreePointAttemptsTests(unittest.TestCase):
    def player(self, attempts):
        return SimpleNamespace(playerId=101, name='Fixture', slot_position='PG', points=44,
            eligibleSlots=['PG'], points_breakdown={'3PM': 3, '3PA': 0},
            stats={'1': {'date': datetime(2026,10,20,23,tzinfo=timezone.utc),
                         'total': {'MIN': 30, **({'3PA': attempts} if attempts is not None else {})}}})

    def test_uses_raw_espn_attempts_not_scoring_contributions_or_makes(self):
        row = _record_for_player(2027,1,SimpleNamespace(team_id=1,team_name='One'),self.player(8))
        self.assertEqual((row['3PA'],row['3PM'],row['FPTS']),(8,3,44))
        self.assertIsNone(_record_for_player(2027,1,SimpleNamespace(team_id=1,team_name='One'),self.player(None))['3PA'])
        self.assertEqual(_record_for_player(2027,1,SimpleNamespace(team_id=1,team_name='One'),self.player(0))['3PA'],0)

    def test_optional_column_preserves_original_history_and_missing_values(self):
        old = daily_period(2026,1)
        promoted = with_raw_three_point_attempts(old)
        pd.testing.assert_frame_equal(promoted.drop(columns='3PA'),old)
        self.assertTrue(promoted['3PA'].isna().all())
        pd.testing.assert_frame_equal(with_raw_three_point_attempts(promoted),promoted)
        validate_player_daily_data(promoted)

    def test_existing_and_new_column_fetch_schemas_remain_supported(self):
        team=SimpleNamespace(team_id=1,team_name='One')
        box=SimpleNamespace(home_team=team,away_team=team,home_lineup=[self.player(8)],away_lineup=[])
        league=SimpleNamespace(box_scores=lambda **kwargs:[box])
        legacy=daily_period(2027,1).columns.tolist()
        self.assertNotIn('3PA',fetch_daily_rows(league,2027,1,1,legacy))
        rows=fetch_daily_rows(league,2027,1,1,legacy+['3PA'])
        self.assertEqual(rows['3PA'].iloc[0],8)
        self.assertEqual(rows['FPTS'].iloc[0],44)

    def test_bounded_refresh_only_populates_authorized_rows_and_is_idempotent(self):
        old=pd.concat([daily_period(2026,1),daily_period(2026,2)],ignore_index=True)
        promoted=with_raw_three_point_attempts(old)
        fetched=promoted[promoted['Scoring Period']==2].copy()
        fetched['3PA']=8.0
        result=replace_partitions(promoted,fetched,{(2026,2)},'Scoring Period',PLAYER_DAILY_KEY,validate_player_daily_data)
        pd.testing.assert_frame_equal(result.drop(columns='3PA'),old)
        self.assertTrue(result.loc[result['Scoring Period']==1,'3PA'].isna().all())
        repeated=replace_partitions(result,fetched,{(2026,2)},'Scoring Period',PLAYER_DAILY_KEY,validate_player_daily_data)
        pd.testing.assert_frame_equal(result,repeated)

    def test_invalid_known_attempts_rejected_but_unknown_is_allowed(self):
        for value in [-1,2.5,'invalid',float('inf')]:
            frame=with_raw_three_point_attempts(daily_period(2026,1));frame['3PA']=value
            with self.subTest(value=value), self.assertRaises(DataValidationError):
                validate_player_daily_data(frame)
