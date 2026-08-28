"""Tests the production merge, validation, and atomic-write boundaries.

No test in this module calls ESPN. The updater modules are imported only to
exercise their real prepare_* and write_* functions with temporary CSV files.
"""

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from dataUpdateSafety import DataValidationError, validate_league_data
from leagueDataUpdater import prepare_league_update, write_league_update
from playerMatchupDataUpdater import prepare_player_matchup_update, write_player_matchup_update


def league_season(year, final_week):
    """Create a complete two-team standings fixture through final_week."""
    rows = []
    totals = {1: [0, 0, 0, 0], 2: [0, 0, 0, 0]}
    for week in range(1, final_week + 1):
        first_points, second_points = (100, 80) if week % 2 else (70, 90)
        first_win = int(first_points > second_points)
        for team_id, opponent_id, points_for, points_against, win in (
            (1, 2, first_points, second_points, first_win),
            (2, 1, second_points, first_points, 1 - first_win),
        ):
            totals[team_id][0] += points_for
            totals[team_id][1] += points_against
            totals[team_id][2] += win
            totals[team_id][3] += 1 - win
            rows.append({
                "Year": year, "Week": week, "Type": "Regular", "Team ID": team_id,
                "Opponent Team ID": opponent_id, "Points For": points_for,
                "Points Against": points_against, "Win": win, "Loss": 1 - win,
                "Cumulative Points For": totals[team_id][0],
                "Cumulative Points Against": totals[team_id][1],
                "Cumulative Wins": totals[team_id][2], "Cumulative Losses": totals[team_id][3],
                "Rank": 1 if win else 2,
            })
    return pd.DataFrame(rows)


def player_week(year, week):
    return pd.DataFrame([
        {"Year": year, "Week": week, "Team ID": 1, "Team Name": "One", "Player ID": 101, "Player Name": "Alpha", "FPTS": 44},
        {"Year": year, "Week": week, "Team ID": 2, "Team Name": "Two", "Player ID": 202, "Player Name": "Bravo", "FPTS": 38},
    ])


class ProductionLeagueUpdateSafetyTests(unittest.TestCase):
    def test_week_14_append_preserves_weeks_1_through_13_exactly(self):
        complete_season = league_season(2025, 14)
        stored = complete_season[complete_season["Week"] <= 13].copy().reset_index(drop=True)
        week_14 = complete_season[complete_season["Week"] == 14].copy().reset_index(drop=True)

        candidate = prepare_league_update(stored, week_14)

        pd.testing.assert_frame_equal(candidate.iloc[:len(stored)].reset_index(drop=True), stored)
        self.assertEqual(set(candidate.iloc[len(stored):]["Week"]), {14})
        self.assertEqual(len(candidate), len(stored) + len(week_14))
        self.assertEqual(candidate.duplicated(["Year", "Week", "Team ID"]).sum(), 0)

    def test_duplicate_week_is_rejected_and_atomic_write_keeps_file_unchanged(self):
        stored = league_season(2025, 13)
        duplicate_week_13 = stored[stored["Week"] == 13].copy()
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "league.csv"
            stored.to_csv(destination, index=False)
            original_bytes = destination.read_bytes()
            with self.assertRaisesRegex(DataValidationError, "overlap"):
                write_league_update(stored, duplicate_week_13, destination)
            self.assertEqual(destination.read_bytes(), original_bytes)

    def test_no_new_rows_is_idempotent_and_does_not_write(self):
        stored = league_season(2025, 13)
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "league.csv"
            stored.to_csv(destination, index=False)
            original_bytes = destination.read_bytes()
            self.assertFalse(write_league_update(stored, stored.iloc[0:0], destination))
            self.assertEqual(destination.read_bytes(), original_bytes)

    def test_production_validation_rejects_bad_rank_missing_rows_and_rollover(self):
        corrupted = league_season(2025, 1)
        corrupted.loc[1, "Rank"] = 3
        with self.assertRaisesRegex(DataValidationError, "invalid ranks"):
            prepare_league_update(corrupted.iloc[0:0], corrupted)

        complete_week = league_season(2025, 1)
        incomplete_week = league_season(2025, 2).iloc[-1:]
        with self.assertRaisesRegex(DataValidationError, "incomplete teams"):
            prepare_league_update(complete_week, incomplete_week)

        prior_week = league_season(2025, 1)
        new_season_week = league_season(2026, 1)
        with self.assertRaisesRegex(DataValidationError, "incomplete"):
            prepare_league_update(prior_week, new_season_week, {2025: 2, 2026: 2})

    def test_production_validator_rejects_missing_required_column(self):
        missing_column = league_season(2025, 1).drop(columns="Rank")
        with self.assertRaisesRegex(DataValidationError, "missing required columns"):
            validate_league_data(missing_column)


class ProductionPlayerMatchupUpdateSafetyTests(unittest.TestCase):
    def test_player_week_append_preserves_history_and_rejects_duplicates(self):
        stored = player_week(2025, 1)
        new_week = player_week(2025, 2)
        candidate = prepare_player_matchup_update(stored, new_week)
        pd.testing.assert_frame_equal(candidate.iloc[:len(stored)].reset_index(drop=True), stored)
        self.assertEqual(set(candidate.iloc[len(stored):]["Week"]), {2})
        with self.assertRaisesRegex(DataValidationError, "overlap"):
            prepare_player_matchup_update(stored, stored.iloc[:1])

    def test_player_invalid_update_does_not_replace_file(self):
        stored = player_week(2025, 1)
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "player.csv"
            stored.to_csv(destination, index=False)
            original_bytes = destination.read_bytes()
            with self.assertRaises(DataValidationError):
                write_player_matchup_update(stored, stored.iloc[:1], destination)
            self.assertEqual(destination.read_bytes(), original_bytes)


if __name__ == "__main__":
    unittest.main()
