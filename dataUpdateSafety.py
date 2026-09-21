"""Shared safeguards for incremental CSV data updates.

Fetching remains in the individual updater modules.  This module only merges
already-fetched rows, validates the proposed dataset, and writes it atomically.
"""

from __future__ import annotations

import math
import os
import tempfile
from collections.abc import Callable, Iterable
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv


# Resolve from this module, not the working directory. Existing environment
# variables (including GitHub Actions Secrets) always take precedence.
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env", override=False)


class DataValidationError(ValueError):
    """An update is invalid and must not replace the persisted dataset."""


def require_espn_credentials() -> tuple[str, str]:
    """Return shared ESPN credentials or raise a clear local setup error."""
    espn_s2 = os.environ.get("ESPN_S2")
    swid = os.environ.get("SWID")
    missing = []
    if not espn_s2:
        missing.append("ESPN_S2")
    if not swid:
        missing.append("SWID")
    if missing:
        raise RuntimeError(
            "Missing ESPN credentials. Set " + ", ".join(missing) + " in the environment or root .env before running a data updater."
        )
    return swid, espn_s2


LEAGUE_KEY = ["Year", "Week", "Team ID"]
PLAYER_MATCHUP_KEY = ["Year", "Week", "Team ID", "Player ID"]
PLAYER_DAILY_KEY = ["Year", "Scoring Period", "Team ID", "Player ID"]

LEAGUE_REQUIRED_COLUMNS = {
    "Year", "Week", "Type", "Team ID", "Points For", "Points Against", "Win", "Loss",
    "Cumulative Points For", "Cumulative Points Against", "Cumulative Wins",
    "Cumulative Losses", "Rank",
}
PLAYER_MATCHUP_REQUIRED_COLUMNS = {
    "Year", "Week", "Team Name", "Team ID", "Player Name", "Player ID", "FPTS",
}
PLAYER_DAILY_REQUIRED_COLUMNS = {
    "Year", "Scoring Period", "Date", "Team Name", "Team ID", "Player Name", "Player ID",
    "Player Slot", "FPTS", "MIN", "FTA", "PTS", "3PM", "BLK", "STL", "AST", "REB",
    "TO", "FGM", "FGA", "FTM", "Position", "Position2", "Position3",
}
PLAYER_DAILY_NUMERIC_COLUMNS = [
    "Year", "Scoring Period", "Team ID", "Player ID", "FPTS", "MIN", "FTA", "PTS", "3PM",
    "BLK", "STL", "AST", "REB", "TO", "FGM", "FGA", "FTM",
]


def _require_columns(frame: pd.DataFrame, required: set[str], dataset_name: str) -> None:
    missing = required.difference(frame.columns)
    if missing:
        raise DataValidationError(f"{dataset_name} is missing required columns: {sorted(missing)}")


def _require_unique_keys(frame: pd.DataFrame, key: list[str], dataset_name: str) -> None:
    duplicates = frame.duplicated(key, keep=False)
    if duplicates.any():
        sample = frame.loc[duplicates, key].head(3).to_dict("records")
        raise DataValidationError(f"{dataset_name} contains duplicate logical records: {sample}")


def _numeric(frame: pd.DataFrame, columns: Iterable[str], dataset_name: str) -> None:
    for column in columns:
        values = pd.to_numeric(frame[column], errors="coerce")
        if values.isna().any():
            raise DataValidationError(f"{dataset_name} has non-numeric {column} values")


def validate_league_data(frame: pd.DataFrame, terminal_week_by_year: dict[int, int] | None = None) -> None:
    """Validate the dashboard's league-data invariants without changing values."""
    _require_columns(frame, LEAGUE_REQUIRED_COLUMNS, "league data")
    _require_unique_keys(frame, LEAGUE_KEY, "league data")
    _numeric(
        frame,
        ["Year", "Week", "Points For", "Points Against", "Win", "Loss", "Cumulative Points For",
         "Cumulative Points Against", "Cumulative Wins", "Cumulative Losses", "Rank"],
        "league data",
    )

    data = frame.copy()
    data["Year"] = pd.to_numeric(data["Year"])
    data["Week"] = pd.to_numeric(data["Week"])
    data["Rank"] = pd.to_numeric(data["Rank"])
    if (data["Week"] < 1).any() or (data["Rank"] < 1).any():
        raise DataValidationError("league data contains an invalid week or rank")
    if not data["Rank"].map(lambda value: float(value).is_integer()).all():
        raise DataValidationError("league data contains a non-integer rank")
    if not data["Win"].isin([0, 1]).all() or not data["Loss"].isin([0, 1]).all():
        raise DataValidationError("league data contains invalid win/loss values")

    # Every league week must contain the complete set of teams for that season.
    expected_teams = data.groupby("Year")["Team ID"].agg(lambda ids: set(ids))
    for (year, week), week_rows in data.groupby(["Year", "Week"], sort=False):
        team_ids = set(week_rows["Team ID"])
        if team_ids != expected_teams.loc[year]:
            raise DataValidationError(f"league data has incomplete teams for {int(year)} week {int(week)}")
        expected_ranks = set(range(1, len(team_ids) + 1))
        actual_ranks = set(week_rows["Rank"].astype(int))
        if actual_ranks != expected_ranks:
            raise DataValidationError(f"league data has invalid ranks for {int(year)} week {int(week)}")

    for (_, _), team_rows in data.groupby(["Year", "Team ID"], sort=False):
        team_rows = team_rows.sort_values("Week")
        expected = {
            "Cumulative Points For": pd.to_numeric(team_rows["Points For"]).cumsum(),
            "Cumulative Points Against": pd.to_numeric(team_rows["Points Against"]).cumsum(),
            "Cumulative Wins": pd.to_numeric(team_rows["Win"]).cumsum(),
            "Cumulative Losses": pd.to_numeric(team_rows["Loss"]).cumsum(),
        }
        for column, totals in expected.items():
            actual = pd.to_numeric(team_rows[column])
            if not all(math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-9) for left, right in zip(actual, totals)):
                raise DataValidationError(f"league data has inconsistent {column}")

    if terminal_week_by_year:
        years = sorted(int(year) for year in data["Year"].unique())
        for year in years[:-1]:
            if year in terminal_week_by_year and data.loc[data["Year"] == year, "Week"].max() != terminal_week_by_year[year]:
                raise DataValidationError(f"season {year} is incomplete before a later season begins")


def validate_player_matchup_data(frame: pd.DataFrame) -> None:
    _require_columns(frame, PLAYER_MATCHUP_REQUIRED_COLUMNS, "player matchup data")
    _require_unique_keys(frame, PLAYER_MATCHUP_KEY, "player matchup data")
    _numeric(frame, ["Year", "Week", "Team ID", "Player ID", "FPTS"], "player matchup data")
    if (pd.to_numeric(frame["Week"]) < 1).any():
        raise DataValidationError("player matchup data contains an invalid week")


def validate_player_daily_data(frame: pd.DataFrame, terminal_period_by_year: dict[int, int] | None = None) -> None:
    """Validate daily-player data without altering its dashboard-compatible schema."""
    _require_columns(frame, PLAYER_DAILY_REQUIRED_COLUMNS, "player daily data")
    _require_unique_keys(frame, PLAYER_DAILY_KEY, "player daily data")
    _numeric(frame, PLAYER_DAILY_NUMERIC_COLUMNS, "player daily data")

    data = frame.copy()
    data["Year"] = pd.to_numeric(data["Year"])
    data["Scoring Period"] = pd.to_numeric(data["Scoring Period"])
    if (data["Scoring Period"] < 1).any() or not data["Scoring Period"].map(lambda value: float(value).is_integer()).all():
        raise DataValidationError("player daily data contains an invalid scoring period")
    try:
        parsed_dates = pd.to_datetime(data["Date"], format="%Y-%m-%d", errors="raise")
    except (TypeError, ValueError) as error:
        raise DataValidationError("player daily data contains an invalid date") from error
    if parsed_dates.isna().any():
        raise DataValidationError("player daily data contains a missing date")

    # ESPN scoring periods represent individual dates in this export.
    dates_per_period = data.groupby(["Year", "Scoring Period"])["Date"].nunique()
    if (dates_per_period > 1).any():
        raise DataValidationError("player daily data maps a scoring period to multiple dates")

    if terminal_period_by_year:
        years = sorted(int(year) for year in data["Year"].unique())
        for year in years[:-1]:
            if year in terminal_period_by_year:
                observed_final_period = data.loc[data["Year"] == year, "Scoring Period"].max()
                if observed_final_period != terminal_period_by_year[year]:
                    raise DataValidationError(f"season {year} is incomplete before a later season begins")


def merge_refreshable_daily_rows(
    existing: pd.DataFrame,
    fetched_rows: pd.DataFrame,
    refresh_period_by_year: dict[int, int],
    terminal_period_by_year: dict[int, int] | None = None,
) -> pd.DataFrame:
    """Replace only named latest daily periods and append later records safely.

    The latest stored scoring period may still be in progress, so its entire
    partition is replaced from ESPN. All earlier periods are immutable; any
    fetched overlap with one of them is rejected before a candidate is built.
    """
    original = existing.copy(deep=True)
    validate_player_daily_data(existing)
    if list(existing.columns) != list(fetched_rows.columns):
        raise DataValidationError("new rows do not match the persisted CSV schema")

    existing_years = pd.to_numeric(existing["Year"])
    existing_periods = pd.to_numeric(existing["Scoring Period"])
    fetched_years = pd.to_numeric(fetched_rows["Year"])
    fetched_periods = pd.to_numeric(fetched_rows["Scoring Period"])
    refresh_existing_mask = pd.Series(False, index=existing.index)
    for year, period in refresh_period_by_year.items():
        refresh_existing_mask |= (existing_years == year) & (existing_periods == period)
        if ((fetched_years == year) & (fetched_periods < period)).any():
            raise DataValidationError(f"daily refresh attempts to modify immutable periods for season {year}")

    immutable_rows = existing.loc[~refresh_existing_mask].copy()
    overlap = immutable_rows.merge(fetched_rows[PLAYER_DAILY_KEY], on=PLAYER_DAILY_KEY, how="inner")
    if not overlap.empty:
        raise DataValidationError("daily refresh overlaps immutable logical records")

    candidate = pd.concat([immutable_rows, fetched_rows], ignore_index=True)
    validate_player_daily_data(candidate, terminal_period_by_year)
    if not existing.equals(original):
        raise DataValidationError("existing rows were mutated during daily refresh")
    return candidate


def merge_incremental_rows(
    existing: pd.DataFrame,
    new_rows: pd.DataFrame,
    key: list[str],
    validator: Callable[..., None],
    *validator_args: object,
) -> pd.DataFrame:
    """Append only new logical records and validate the complete candidate.

    Existing rows are never recalculated, replaced, or reordered. An overlap is
    an error rather than an implicit overwrite, making repeated runs idempotent
    when callers pass an empty `new_rows` after discovering no new week.
    """
    original = existing.copy(deep=True)
    validator(existing, *validator_args)
    if new_rows.empty:
        return existing.copy(deep=True)
    if list(existing.columns) != list(new_rows.columns):
        raise DataValidationError("new rows do not match the persisted CSV schema")
    overlap = existing.merge(new_rows[key], on=key, how="inner")
    if not overlap.empty:
        raise DataValidationError("new rows overlap existing logical records")
    candidate = pd.concat([existing, new_rows], ignore_index=True)
    validator(candidate, *validator_args)
    if not existing.equals(original):
        raise DataValidationError("existing rows were mutated during merge")
    return candidate


def atomic_write_csv(frame: pd.DataFrame, destination: str | Path) -> None:
    """Write a fully validated DataFrame via a same-directory temporary file."""
    path = Path(destination)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", prefix=f".{path.stem}-", dir=path.parent, delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        frame.to_csv(temporary_path, index=False)
        os.replace(temporary_path, path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
