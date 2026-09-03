"""Contract tests for future incremental league and player-matchup updaters.

The production updaters currently call ESPN and write CSVs directly, so these
tests use small in-memory records only.  They define the validation contract an
updater must satisfy before it is allowed to replace a data file.
"""

import csv
import tempfile
import unittest
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path


class DataValidationError(ValueError):
    """Raised when a proposed incremental dataset is unsafe to write."""


LEAGUE_COLUMNS = {
    "Year", "Week", "Type", "Team ID", "Points For", "Points Against",
    "Win", "Loss", "Opponent Team ID", "Cumulative Points For",
    "Cumulative Points Against", "Cumulative Wins", "Cumulative Losses", "Rank",
}
PLAYER_MATCHUP_COLUMNS = {
    "Year", "Week", "Team ID", "Player ID", "Player Name", "FPTS",
}

# A league record describes one fantasy team in one matchup week.  Even a bye
# gets a team-week row, so this key prevents double-counting standings data.
LEAGUE_KEY = ("Year", "Week", "Team ID")
# A player may appear for a different team in a later week, but only once for a
# particular fantasy team in a particular week.
PLAYER_MATCHUP_KEY = ("Year", "Week", "Team ID", "Player ID")


def key_for(row, key_fields):
    return tuple(row[field] for field in key_fields)


def duplicate_keys(rows, key_fields):
    counts = Counter(key_for(row, key_fields) for row in rows)
    return [key for key, count in counts.items() if count > 1]


def require_columns(rows, required_columns, dataset_name):
    if not rows:
        raise DataValidationError(f"{dataset_name} has no rows")
    missing = required_columns - set(rows[0])
    if missing:
        raise DataValidationError(f"{dataset_name} is missing columns: {sorted(missing)}")


def validate_player_matchup_rows(rows):
    require_columns(rows, PLAYER_MATCHUP_COLUMNS, "player matchup data")
    duplicates = duplicate_keys(rows, PLAYER_MATCHUP_KEY)
    if duplicates:
        raise DataValidationError(f"duplicate player-matchup keys: {duplicates[:3]}")
    for row in rows:
        try:
            float(row["FPTS"])
        except (TypeError, ValueError) as error:
            raise DataValidationError(f"invalid FPTS for {key_for(row, PLAYER_MATCHUP_KEY)}") from error


def validate_league_rows(rows, expected_team_ids_by_year):
    """Validate standings, team counts, ranks, and cumulative totals."""
    require_columns(rows, LEAGUE_COLUMNS, "league data")
    duplicates = duplicate_keys(rows, LEAGUE_KEY)
    if duplicates:
        raise DataValidationError(f"duplicate league keys: {duplicates[:3]}")

    rows_by_week = defaultdict(list)
    rows_by_team = defaultdict(list)
    for row in rows:
        try:
            year, week, rank = int(row["Year"]), int(row["Week"]), int(row["Rank"])
            if week < 1 or rank < 1:
                raise ValueError
            for field in ("Points For", "Points Against", "Cumulative Points For", "Cumulative Points Against", "Cumulative Wins", "Cumulative Losses"):
                float(row[field])
            if float(row["Win"]) not in (0, 1) or float(row["Loss"]) not in (0, 1):
                raise ValueError
        except (TypeError, ValueError) as error:
            raise DataValidationError(f"invalid league values for {key_for(row, LEAGUE_KEY)}") from error
        rows_by_week[(year, week)].append(row)
        rows_by_team[(year, row["Team ID"])].append(row)

    for (year, week), week_rows in rows_by_week.items():
        expected_ids = expected_team_ids_by_year[year]
        actual_ids = {row["Team ID"] for row in week_rows}
        if actual_ids != expected_ids:
            raise DataValidationError(
                f"{year} week {week} has teams {sorted(actual_ids)}, expected {sorted(expected_ids)}"
            )
        ranks = {int(row["Rank"]) for row in week_rows}
        expected_ranks = set(range(1, len(expected_ids) + 1))
        if ranks != expected_ranks:
            raise DataValidationError(f"{year} week {week} has invalid ranks {sorted(ranks)}")

    for team_rows in rows_by_team.values():
        points_for = points_against = wins = losses = 0.0
        for row in sorted(team_rows, key=lambda item: int(item["Week"])):
            points_for += float(row["Points For"])
            points_against += float(row["Points Against"])
            wins += float(row["Win"])
            losses += float(row["Loss"])
            actual = (
                float(row["Cumulative Points For"]), float(row["Cumulative Points Against"]),
                float(row["Cumulative Wins"]), float(row["Cumulative Losses"]),
            )
            expected = (points_for, points_against, wins, losses)
            if actual != expected:
                raise DataValidationError(f"cumulative totals do not match for {key_for(row, LEAGUE_KEY)}")


def merge_incrementally(existing_rows, new_rows, key_fields, validate_rows, *validator_args):
    """Return a validated append-only candidate without touching any CSV file."""
    existing_snapshot = deepcopy(existing_rows)
    candidate = deepcopy(existing_rows) + deepcopy(new_rows)
    validate_rows(candidate, *validator_args)
    if existing_rows != existing_snapshot:
        raise DataValidationError("existing rows were mutated while building an update")
    return candidate


def validate_rollover(rows, terminal_week_by_year):
    """A later season cannot start until every earlier configured season is complete."""
    weeks_by_year = defaultdict(set)
    for row in rows:
        weeks_by_year[int(row["Year"])].add(int(row["Week"]))
    years = sorted(weeks_by_year)
    for year in years[:-1]:
        if max(weeks_by_year[year]) != terminal_week_by_year[year]:
            raise DataValidationError(f"season {year} is incomplete before season {year + 1} begins")


def write_validated_candidate(path, existing_rows, new_rows, key_fields, validate_rows, *validator_args):
    """Test-only write boundary: validate first, then replace the supplied file."""
    candidate = merge_incrementally(existing_rows, new_rows, key_fields, validate_rows, *validator_args)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(candidate[0]))
        writer.writeheader()
        writer.writerows(candidate)


def league_row(year, week, team_id, opponent_id, points_for, points_against, win, loss, rank, cumulative):
    return {
        "Year": str(year), "Week": str(week), "Type": "Regular", "Team ID": str(team_id),
        "Opponent Team ID": str(opponent_id), "Points For": str(points_for),
        "Points Against": str(points_against), "Win": str(win), "Loss": str(loss),
        "Rank": str(rank), "Cumulative Points For": str(cumulative[0]),
        "Cumulative Points Against": str(cumulative[1]), "Cumulative Wins": str(cumulative[2]),
        "Cumulative Losses": str(cumulative[3]),
    }


def player_row(year, week, team_id, player_id, points):
    return {
        "Year": str(year), "Week": str(week), "Team ID": str(team_id),
        "Player ID": str(player_id), "Player Name": f"Player {player_id}", "FPTS": str(points),
    }


def two_team_league_week(year, week, first_score, second_score, first_cumulative, second_cumulative):
    first_win = int(first_score > second_score)
    return [
        league_row(year, week, 1, 2, first_score, second_score, first_win, 1 - first_win, 1 if first_win else 2, first_cumulative),
        league_row(year, week, 2, 1, second_score, first_score, 1 - first_win, first_win, 2 if first_win else 1, second_cumulative),
    ]


class IncrementalLeagueUpdateTests(unittest.TestCase):
    def setUp(self):
        self.expected_teams = {2025: {"1", "2"}, 2026: {"1", "2"}}
        self.week_one = two_team_league_week(2025, 1, 100, 80, (100, 80, 1, 0), (80, 100, 0, 1))
        self.week_two = two_team_league_week(2025, 2, 70, 90, (170, 170, 1, 1), (170, 170, 1, 1))

    def test_new_week_preserves_all_historical_rows(self):
        candidate = merge_incrementally(self.week_one, self.week_two, LEAGUE_KEY, validate_league_rows, self.expected_teams)
        self.assertEqual(candidate[:len(self.week_one)], self.week_one)
        self.assertEqual(candidate[len(self.week_one):], self.week_two)

    def test_adding_week_n_only_adds_expected_week_n_records(self):
        candidate = merge_incrementally(self.week_one, self.week_two, LEAGUE_KEY, validate_league_rows, self.expected_teams)
        new_rows = candidate[len(self.week_one):]
        self.assertEqual({row["Week"] for row in new_rows}, {"2"})
        self.assertEqual({row["Team ID"] for row in new_rows}, {"1", "2"})
        self.assertEqual({key_for(row, LEAGUE_KEY) for row in candidate[:2]}, {("2025", "1", "1"), ("2025", "1", "2")})

    def test_repeating_the_same_week_is_rejected_before_it_can_duplicate(self):
        with self.assertRaisesRegex(DataValidationError, "duplicate league keys"):
            merge_incrementally(self.week_one + self.week_two, self.week_two, LEAGUE_KEY, validate_league_rows, self.expected_teams)

    def test_league_week_requires_all_teams_even_when_playoffs_have_byes(self):
        expected_teams = {2025: {"1", "2", "3", "4"}}
        playoff_week = [
            *two_team_league_week(2025, 1, 100, 80, (100, 80, 1, 0), (80, 100, 0, 1)),
            {**league_row(2025, 1, 3, "", 0, 0, 0, 0, 3, (0, 0, 0, 0)), "Type": "Bye"},
            {**league_row(2025, 1, 4, "", 0, 0, 0, 0, 4, (0, 0, 0, 0)), "Type": "Bye"},
        ]
        validate_league_rows(playoff_week, expected_teams)
        with self.assertRaisesRegex(DataValidationError, "expected"):
            validate_league_rows(playoff_week[:-1], expected_teams)

    def test_cumulative_totals_and_weekly_ranks_are_checked_after_update(self):
        candidate = merge_incrementally(self.week_one, self.week_two, LEAGUE_KEY, validate_league_rows, self.expected_teams)
        self.assertEqual(candidate[-1]["Cumulative Wins"], "1")
        corrupted = deepcopy(candidate)
        corrupted[-1]["Cumulative Points For"] = "999"
        with self.assertRaisesRegex(DataValidationError, "cumulative totals"):
            validate_league_rows(corrupted, self.expected_teams)
        corrupted = deepcopy(candidate)
        corrupted[-1]["Rank"] = "3"
        with self.assertRaisesRegex(DataValidationError, "invalid ranks"):
            validate_league_rows(corrupted, self.expected_teams)

    def test_historical_seasons_are_unchanged_when_current_season_is_added(self):
        history = two_team_league_week(2024, 1, 75, 50, (75, 50, 1, 0), (50, 75, 0, 1))
        expected_teams = {2024: {"1", "2"}, 2025: {"1", "2"}}
        candidate = merge_incrementally(history, self.week_one, LEAGUE_KEY, validate_league_rows, expected_teams)
        self.assertEqual([row for row in candidate if row["Year"] == "2024"], history)

    def test_rollover_requires_previous_season_to_be_completed_first(self):
        current_season_week = two_team_league_week(2026, 1, 95, 70, (95, 70, 1, 0), (70, 95, 0, 1))
        terminal_weeks = {2025: 2, 2026: 2}
        with self.assertRaisesRegex(DataValidationError, "incomplete"):
            validate_rollover(self.week_one + current_season_week, terminal_weeks)
        validate_rollover(self.week_one + self.week_two + current_season_week, terminal_weeks)


class IncrementalPlayerMatchupUpdateTests(unittest.TestCase):
    def setUp(self):
        self.week_one = [player_row(2025, 1, 1, 101, 44), player_row(2025, 1, 2, 202, 38)]
        self.week_two = [player_row(2025, 2, 1, 101, 49), player_row(2025, 2, 2, 202, 42)]

    def test_new_week_preserves_existing_player_records(self):
        candidate = merge_incrementally(self.week_one, self.week_two, PLAYER_MATCHUP_KEY, validate_player_matchup_rows)
        self.assertEqual(candidate[:len(self.week_one)], self.week_one)
        self.assertEqual({row["Week"] for row in candidate[len(self.week_one):]}, {"2"})

    def test_repeating_same_player_team_week_is_rejected(self):
        with self.assertRaisesRegex(DataValidationError, "duplicate player-matchup keys"):
            merge_incrementally(self.week_one, [player_row(2025, 1, 1, 101, 44)], PLAYER_MATCHUP_KEY, validate_player_matchup_rows)


class CorruptUpdateWriteProtectionTests(unittest.TestCase):
    def setUp(self):
        self.expected_teams = {2025: {"1", "2"}}
        self.existing = two_team_league_week(2025, 1, 100, 80, (100, 80, 1, 0), (80, 100, 0, 1))

    def test_invalid_update_does_not_overwrite_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "league.csv"
            write_validated_candidate(path, [], self.existing, LEAGUE_KEY, validate_league_rows, self.expected_teams)
            original_contents = path.read_text(encoding="utf-8")
            with self.assertRaises(DataValidationError):
                write_validated_candidate(path, self.existing, [self.existing[0]], LEAGUE_KEY, validate_league_rows, self.expected_teams)
            self.assertEqual(path.read_text(encoding="utf-8"), original_contents)

    def test_missing_columns_and_unexpected_row_counts_fail_validation(self):
        missing_column = deepcopy(self.existing)
        del missing_column[0]["Rank"]
        with self.assertRaisesRegex(DataValidationError, "missing columns"):
            validate_league_rows(missing_column, self.expected_teams)
        with self.assertRaisesRegex(DataValidationError, "expected"):
            validate_league_rows(self.existing[:1], self.expected_teams)


if __name__ == "__main__":
    unittest.main()
