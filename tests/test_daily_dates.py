"""UTC-runner regression from actual ESPN timestamps; no network calls."""
from contextlib import contextmanager
from datetime import datetime
import json
import os
from pathlib import Path
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import pandas as pd

from dataUpdateSafety import DataValidationError, PLAYER_DAILY_KEY, validate_player_daily_data
from nearLiveSafety import replace_partitions
from playerDailyDataUpdater import _record_for_player, fetch_daily_rows
from tests.test_production_update_safety import daily_period

SAMPLES = json.loads((Path(__file__).parent / 'fixtures/daily_game_dates.json').read_text())['samples']


@contextmanager
def host_timezone(name):
    try:
        with patch.dict(os.environ, {'TZ': name}):
            time.tzset()
            yield
    finally:
        time.tzset()


def player(sample, aware=False):
    instant = datetime.fromisoformat(sample['utc'])
    stamp = instant if aware else datetime.fromtimestamp(instant.timestamp())
    stats = daily_period(sample['year'], 1).iloc[0].to_dict()
    breakdown = {key: stats[key] for key in ('FTA', 'PTS', '3PM', 'BLK', 'STL', 'AST', 'REB', 'TO', 'FGM', 'FGA', 'FTM')}
    return SimpleNamespace(playerId=sample['playerId'], name='Fixture player', points=44,
        slot_position='PG', eligibleSlots=['PG'], points_breakdown=breakdown,
        stats={str(sample['period']): {'date': stamp, 'total': {'MIN': 30}}})


class DailyDateTests(unittest.TestCase):
    def test_actual_utc_failure_is_reproduced_and_source_conversion_fixes_it(self):
        with host_timezone('UTC'):
            samples = [s for s in SAMPLES if s['year'] == 2026]
            team = SimpleNamespace(team_id=1, team_name='One')
            players = [player(s) for s in samples]
            box = SimpleNamespace(home_team=team, away_team=team, home_lineup=players, away_lineup=[])
            league = SimpleNamespace(box_scores=lambda **kw: [box])
            rows = fetch_daily_rows(league, 2026, 161, 161, daily_period(2026, 1).columns.tolist())
            wrong = rows.copy()
            wrong['Date'] = [p.stats['161']['date'].date().isoformat() for p in players]
            with self.assertRaises(DataValidationError) as caught:
                validate_player_daily_data(wrong, source='fresh ESPN')
            for expected in ('fresh ESPN', '2026', '161', '2026-03-30', '2026-03-31', '2490149', '3908809'):
                self.assertIn(expected, str(caught.exception))
            validate_player_daily_data(rows)
            self.assertEqual(set(rows.Date), {'2026-03-30'})
            self.assertEqual(len(rows), len(wrong))
            pd.testing.assert_frame_equal(rows.drop(columns='Date'), wrong.drop(columns='Date'))

    def test_host_timezone_does_not_change_saved_game_dates(self):
        team = SimpleNamespace(team_id=1, team_name='One')
        for zone in ('UTC', 'America/New_York', 'America/Los_Angeles'):
            with self.subTest(zone=zone), host_timezone(zone):
                for sample in SAMPLES:
                    row = _record_for_player(sample['year'], sample['period'], team, player(sample))
                    self.assertEqual(row['Date'], sample['leagueDate'])
                    self.assertEqual(row['Scoring Period'], sample['period'])
                    aware = _record_for_player(sample['year'], sample['period'], team, player(sample, aware=True))
                    self.assertEqual(aware, row)

    def test_reused_period_numbers_across_seasons_are_valid(self):
        rows = pd.concat([daily_period(2026, 1), daily_period(2027, 1)], ignore_index=True)
        validate_player_daily_data(rows)
        rows.loc[1, 'Date'] = '2026-10-02'
        with self.assertRaises(DataValidationError):
            validate_player_daily_data(rows)

    def test_fixed_dates_keep_history_corrections_and_idempotence(self):
        history = daily_period(2025, 1)
        current = daily_period(2026, 1)
        current['Scoring Period'] = 161
        current['Date'] = '2026-03-30'
        existing = pd.concat([history, current], ignore_index=True)
        with host_timezone('UTC'):
            team = SimpleNamespace(team_id=1, team_name='One')
            fetched = pd.DataFrame([_record_for_player(2026, 161, team, player(s)) for s in SAMPLES if s['year'] == 2026],
                                   columns=existing.columns)
        candidate = replace_partitions(existing, fetched, {(2026, 161)}, 'Scoring Period', PLAYER_DAILY_KEY, validate_player_daily_data)
        pd.testing.assert_frame_equal(candidate.iloc[:len(history)], history)
        repeated = replace_partitions(candidate, fetched, {(2026, 161)}, 'Scoring Period', PLAYER_DAILY_KEY, validate_player_daily_data)
        pd.testing.assert_frame_equal(candidate, repeated)
        corrected = fetched.copy()
        corrected.loc[0, 'FPTS'] += 1
        result = replace_partitions(candidate, corrected, {(2026, 161)}, 'Scoring Period', PLAYER_DAILY_KEY, validate_player_daily_data)
        self.assertEqual(result.FPTS.sum(), candidate.FPTS.sum() + 1)
        pd.testing.assert_frame_equal(result.iloc[:len(history)], history)
