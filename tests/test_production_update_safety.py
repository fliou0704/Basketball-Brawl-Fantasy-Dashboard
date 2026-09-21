"""Tests the production merge, validation, and atomic-write boundaries.

No test in this module calls ESPN. The updater modules are imported only to
exercise their real prepare_* and write_* functions with temporary CSV files.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from dataUpdateSafety import (
    DataValidationError,
    require_espn_credentials,
    validate_league_data,
    validate_player_daily_data,
)
from leagueDataUpdater import prepare_league_update, write_league_update
from playerDailyDataUpdater import (
    available_scoring_period,
    fetch_daily_rows,
    prepare_player_daily_update,
    write_player_daily_update,
)
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


def daily_period(year, scoring_period):
    date = f"{year}-10-{scoring_period:02d}"
    rows = []
    for team_id, player_id, player_name, points in ((1, 101, "Alpha", 44), (2, 202, "Bravo", 38)):
        rows.append({
            "Year": year, "Scoring Period": scoring_period, "Date": date,
            "Team Name": f"Team {team_id}", "Team ID": team_id, "Player Name": player_name,
            "Player ID": player_id, "Player Slot": "PG", "FPTS": points, "MIN": 30,
            "Position": "PG", "Position2": None, "Position3": None,
            "FTA": 2, "PTS": 20, "3PM": 2, "BLK": 0, "STL": 1, "AST": 5, "REB": 4,
            "TO": 2, "FGM": 8, "FGA": 15, "FTM": 2,
        })
    return pd.DataFrame(rows)


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


class ProductionPlayerDailyUpdateSafetyTests(unittest.TestCase):
    def test_daily_append_preserves_history_and_adds_only_new_period(self):
        stored = pd.concat([daily_period(2025, 1), daily_period(2025, 2)], ignore_index=True)
        new_period = daily_period(2025, 3)
        candidate = prepare_player_daily_update(stored, new_period)
        pd.testing.assert_frame_equal(candidate.iloc[:len(stored)].reset_index(drop=True), stored)
        self.assertEqual(set(candidate.iloc[len(stored):]["Scoring Period"]), {3})
        self.assertEqual(candidate.duplicated(["Year", "Scoring Period", "Team ID", "Player ID"]).sum(), 0)

    def test_daily_rerun_with_no_records_is_idempotent(self):
        stored = daily_period(2025, 1)
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "daily.csv"
            stored.to_csv(destination, index=False)
            original_bytes = destination.read_bytes()
            self.assertFalse(write_player_daily_update(stored, stored.iloc[0:0], destination))
            self.assertEqual(destination.read_bytes(), original_bytes)

    def test_latest_period_is_refreshed_with_removed_and_new_espn_rows(self):
        first_period = daily_period(2025, 1)
        stored_latest = daily_period(2025, 2)
        stored = pd.concat([first_period, stored_latest], ignore_index=True)
        refreshed = stored_latest.iloc[:1].copy()
        refreshed.loc[:, "FPTS"] = 55  # an in-progress score changed
        new_player = refreshed.copy()
        new_player.loc[:, "Player ID"] = 303
        new_player.loc[:, "Player Name"] = "Charlie"
        refreshed = pd.concat([refreshed, new_player], ignore_index=True)

        candidate = prepare_player_daily_update(
            stored, refreshed, refresh_period_by_year={2025: 2}
        )

        pd.testing.assert_frame_equal(
            candidate[candidate["Scoring Period"] == 1].reset_index(drop=True),
            first_period.reset_index(drop=True),
        )
        latest = candidate[candidate["Scoring Period"] == 2]
        self.assertEqual(set(latest["Player ID"]), {101, 303})
        self.assertEqual(latest.loc[latest["Player ID"] == 101, "FPTS"].iloc[0], 55)
        self.assertNotIn(202, set(latest["Player ID"]))

    def test_refresh_cannot_modify_a_period_before_the_boundary(self):
        stored = pd.concat([daily_period(2025, 1), daily_period(2025, 2)], ignore_index=True)
        attempted_rewrite = pd.concat([daily_period(2025, 1), daily_period(2025, 2)], ignore_index=True)
        attempted_rewrite.loc[0, "FPTS"] = 999
        with self.assertRaisesRegex(DataValidationError, "immutable periods"):
            prepare_player_daily_update(stored, attempted_rewrite, refresh_period_by_year={2025: 2})

    def test_refreshes_previous_final_period_while_adding_next_period(self):
        first_period = daily_period(2025, 1)
        stored_latest = daily_period(2025, 2)
        stored = pd.concat([first_period, stored_latest], ignore_index=True)
        final_refresh = stored_latest.copy()
        final_refresh.loc[:, "FPTS"] = 60
        advanced_period = daily_period(2025, 3)
        candidate = prepare_player_daily_update(
            stored,
            pd.concat([final_refresh, advanced_period], ignore_index=True),
            refresh_period_by_year={2025: 2},
        )
        pd.testing.assert_frame_equal(
            candidate[candidate["Scoring Period"] == 1].reset_index(drop=True),
            first_period.reset_index(drop=True),
        )
        self.assertEqual(set(candidate["Scoring Period"]), {1, 2, 3})
        self.assertTrue((candidate[candidate["Scoring Period"] == 2]["FPTS"] == 60).all())

    def test_final_period_is_refreshed_before_season_rollover(self):
        prior_final = daily_period(2025, 1)
        refreshed_final = prior_final.copy()
        refreshed_final.loc[:, "FPTS"] = 70
        new_season = daily_period(2026, 1)
        candidate = prepare_player_daily_update(
            prior_final,
            pd.concat([refreshed_final, new_season], ignore_index=True),
            terminal_period_by_year={2025: 1, 2026: 1},
            refresh_period_by_year={2025: 1},
        )
        self.assertEqual(set(candidate["Year"]), {2025, 2026})
        self.assertTrue((candidate[candidate["Year"] == 2025]["FPTS"] == 70).all())

    def test_identical_latest_period_refresh_does_not_write(self):
        stored = pd.concat([daily_period(2025, 1), daily_period(2025, 2)], ignore_index=True)
        identical_refresh = stored[stored["Scoring Period"] == 2].copy()
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "daily.csv"
            stored.to_csv(destination, index=False)
            original_bytes = destination.read_bytes()
            self.assertFalse(
                write_player_daily_update(
                    stored, identical_refresh, destination, refresh_period_by_year={2025: 2}
                )
            )
            self.assertEqual(destination.read_bytes(), original_bytes)

    def test_invalid_refresh_leaves_file_byte_for_byte_unchanged(self):
        stored = pd.concat([daily_period(2025, 1), daily_period(2025, 2)], ignore_index=True)
        invalid_refresh = stored[stored["Scoring Period"] == 2].copy()
        invalid_refresh.iloc[0, invalid_refresh.columns.get_loc("Date")] = "not-a-date"
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "daily.csv"
            stored.to_csv(destination, index=False)
            original_bytes = destination.read_bytes()
            with self.assertRaisesRegex(DataValidationError, "invalid date"):
                write_player_daily_update(
                    stored, invalid_refresh, destination, refresh_period_by_year={2025: 2}
                )
            self.assertEqual(destination.read_bytes(), original_bytes)

    def test_duplicate_or_invalid_daily_update_does_not_replace_file(self):
        stored = daily_period(2025, 1)
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "daily.csv"
            stored.to_csv(destination, index=False)
            original_bytes = destination.read_bytes()
            with self.assertRaisesRegex(DataValidationError, "overlap"):
                write_player_daily_update(stored, stored.iloc[:1], destination)
            invalid = daily_period(2025, 2)
            invalid.loc[0, "Date"] = "not-a-date"
            with self.assertRaisesRegex(DataValidationError, "invalid date"):
                write_player_daily_update(stored, invalid, destination)
            self.assertEqual(destination.read_bytes(), original_bytes)

    def test_daily_season_rollover_requires_prior_season_completion(self):
        prior_incomplete = daily_period(2025, 1)
        new_season = daily_period(2026, 1)
        with self.assertRaisesRegex(DataValidationError, "incomplete"):
            prepare_player_daily_update(prior_incomplete, new_season, {2025: 2, 2026: 2})
        prior_complete = pd.concat([daily_period(2025, 1), daily_period(2025, 2)], ignore_index=True)
        candidate = prepare_player_daily_update(prior_complete, new_season, {2025: 2, 2026: 2})
        self.assertEqual(set(candidate["Year"]), {2025, 2026})

    def test_fetch_boundary_requests_only_missing_periods(self):
        class FakeLeague:
            def __init__(self):
                self.periods = []

            def box_scores(self, scoring_period, matchup_total):
                self.periods.append((scoring_period, matchup_total))
                return []

        league = FakeLeague()
        rows = fetch_daily_rows(league, 2025, 14, 16, daily_period(2025, 1).columns.tolist())
        self.assertTrue(rows.empty)
        self.assertEqual(league.periods, [(14, False), (15, False), (16, False)])

    def test_periods_after_final_scoring_period_are_never_fetched(self):
        class FakeLeague:
            scoringPeriodId = 175
            finalScoringPeriod = 167

            def __init__(self):
                self.periods = []

            def box_scores(self, scoring_period, matchup_total):
                self.periods.append(scoring_period)
                return []

        league = FakeLeague()
        terminal_period = available_scoring_period(league)
        rows = fetch_daily_rows(league, 2025, 166, terminal_period, daily_period(2025, 1).columns.tolist())
        self.assertTrue(rows.empty)
        self.assertEqual(terminal_period, 167)
        self.assertEqual(league.periods, [166, 167])

    def test_final_scoring_period_allows_completed_season_rollover(self):
        completed_prior_season = daily_period(2025, 1).copy()
        completed_prior_season.loc[:, "Scoring Period"] = 167
        new_season = daily_period(2026, 1)
        # ESPN may expose a later global scoring period (e.g. 175), but the
        # fantasy season completed at its declared final scoring period (167).
        candidate = prepare_player_daily_update(
            completed_prior_season,
            new_season,
            terminal_period_by_year={2025: 167, 2026: 167},
        )
        self.assertEqual(set(candidate["Year"]), {2025, 2026})


class ProductionCredentialConfigurationTests(unittest.TestCase):
    def test_missing_credentials_raise_a_clear_error_before_an_espn_call(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "ESPN_S2.*SWID"):
                require_espn_credentials()

    def test_configured_credentials_are_returned(self):
        with patch.dict("os.environ", {"SWID": "test-swid", "ESPN_S2": "default"}, clear=True):
            self.assertEqual(require_espn_credentials(), ("test-swid", "default"))


if __name__ == "__main__":
    unittest.main()
