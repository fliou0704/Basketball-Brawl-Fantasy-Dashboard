"""Regression checks for the CSV datasets used by the dashboard.

These tests deliberately use only Python's standard library.  They can run in
CI or on a new machine without ESPN credentials or a network connection.
"""

import csv
import datetime as dt
import unittest
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

DATASETS = {
    "league": {
        "filename": "basketballBrawlLeagueData.csv",
        "required_columns": {
            "Year", "Week", "Type", "Team Name", "Team ID", "Points For",
            "Points Against", "Win", "Loss", "Opponent Team ID", "Rank",
        },
        # One team should appear once in a season/week, including a bye.
        "unique_key": ("Year", "Week", "Team ID"),
    },
    "player_matchup": {
        "filename": "playerMatchupData.csv",
        "required_columns": {
            "Year", "Week", "Team Name", "Team ID", "Player Name", "Player ID", "FPTS",
        },
        "unique_key": ("Year", "Week", "Team ID", "Player ID"),
    },
    "player_daily": {
        "filename": "playerDailyData.csv",
        "required_columns": {
            "Year", "Scoring Period", "Date", "Team Name", "Team ID", "Player Name",
            "Player ID", "Player Slot", "FPTS", "MIN",
        },
        "unique_key": ("Year", "Scoring Period", "Team ID", "Player ID"),
    },
    "activity": {
        "filename": "activityData.csv",
        "required_columns": {"Year", "Date", "Time", "Team Name", "Asset", "Action", "Team ID", "Player ID"},
        # Activity can contain multiple actions for a player, so the event fields belong in its key.
        "unique_key": ("Year", "Date", "Time", "Team ID", "Player ID", "Action", "Asset"),
    },
}


def read_dataset(name):
    with (DATA_DIR / DATASETS[name]["filename"]).open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def canonical_id(value):
    """Make CSV IDs comparable when pandas has serialized them as e.g. '7.0'."""
    return str(int(float(value))) if value else ""


class DataValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = {name: read_dataset(name) for name in DATASETS}

    def test_required_data_files_and_columns_exist(self):
        for name, spec in DATASETS.items():
            path = DATA_DIR / spec["filename"]
            self.assertTrue(path.is_file(), f"Missing required dataset: {path}")
            self.assertGreater(len(self.rows[name]), 0, f"{name} must not be empty")
            self.assertTrue(
                spec["required_columns"].issubset(self.rows[name][0]),
                f"{name} is missing required columns",
            )

    def test_headers_do_not_repeat_columns(self):
        for name, spec in DATASETS.items():
            with (DATA_DIR / spec["filename"]).open(newline="", encoding="utf-8") as file:
                headers = next(csv.reader(file))
            self.assertEqual(len(headers), len(set(headers)), f"{name} has duplicate column names")

    def test_no_duplicate_exact_rows(self):
        """Protect against accidentally appending an identical export twice."""
        for name, rows in self.rows.items():
            records = [tuple(row.items()) for row in rows]
            duplicates = [record for record, count in Counter(records).items() if count > 1]
            self.assertFalse(duplicates, f"{name} contains duplicate full rows")

    def test_no_duplicate_data_records(self):
        """Each dataset has a stable logical key; duplicate keys would double-count stats."""
        for name, spec in DATASETS.items():
            key_fields = spec["unique_key"]
            keys = [tuple(row[field] for field in key_fields) for row in self.rows[name]]
            duplicates = [key for key, count in Counter(keys).items() if count > 1]
            self.assertFalse(duplicates, f"{name} has duplicate record keys: {duplicates[:3]}")

    def test_league_matchups_are_reciprocal(self):
        league_rows = self.rows["league"]
        by_team_week = {
            (row["Year"], row["Week"], canonical_id(row["Team ID"])): row
            for row in league_rows
        }
        for row in league_rows:
            if row["Type"] == "Bye":
                continue
            opponent = by_team_week.get(
                (row["Year"], row["Week"], canonical_id(row["Opponent Team ID"]))
            )
            self.assertIsNotNone(opponent, f"Missing opponent for {row['Year']} week {row['Week']}")
            self.assertEqual(canonical_id(opponent["Opponent Team ID"]), canonical_id(row["Team ID"]))
            self.assertEqual(float(opponent["Points For"]), float(row["Points Against"]))
            self.assertEqual(float(opponent["Points Against"]), float(row["Points For"]))

    def test_player_records_reference_a_known_league_team(self):
        league_team_seasons = {
            (row["Year"], canonical_id(row["Team ID"])) for row in self.rows["league"]
        }
        for name in ("player_matchup", "player_daily", "activity"):
            for row in self.rows[name]:
                key = (row["Year"], canonical_id(row["Team ID"]))
                self.assertIn(key, league_team_seasons, f"{name} references unknown team-season {key}")

    def test_score_fields_and_ranks_are_numeric_and_sensible(self):
        for row in self.rows["league"]:
            self.assertGreaterEqual(float(row["Points For"]), 0)
            self.assertGreaterEqual(float(row["Points Against"]), 0)
            self.assertIn(float(row["Win"]), (0, 1))
            self.assertIn(float(row["Loss"]), (0, 1))
            self.assertGreaterEqual(int(float(row["Rank"])), 1)

        for name in ("player_matchup", "player_daily"):
            for row in self.rows[name]:
                float(row["FPTS"])

    def test_dates_are_parseable(self):
        for row in self.rows["player_daily"]:
            dt.date.fromisoformat(row["Date"])

        for row in self.rows["activity"]:
            try:
                dt.date.fromisoformat(row["Date"])
            except ValueError:
                dt.datetime.strptime(row["Date"], "%m/%d/%Y")
            dt.datetime.strptime(row["Time"], "%H:%M")


if __name__ == "__main__":
    unittest.main()
