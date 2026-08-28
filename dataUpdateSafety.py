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


class DataValidationError(ValueError):
    """An update is invalid and must not replace the persisted dataset."""


def require_espn_credentials(year: int | None = None) -> tuple[str, str]:
    """Return configured ESPN credentials or raise a clear local setup error.

    ``ESPN_S2_<YEAR>`` may be supplied for a historical season that requires a
    different session; ``ESPN_S2`` is the normal fallback.
    """
    espn_s2 = os.environ.get(f"ESPN_S2_{year}") if year else None
    espn_s2 = espn_s2 or os.environ.get("ESPN_S2")
    swid = os.environ.get("SWID")
    missing = []
    if not espn_s2:
        missing.append(f"ESPN_S2_{year} or ESPN_S2" if year else "ESPN_S2")
    if not swid:
        missing.append("SWID")
    if missing:
        raise RuntimeError(
            "Missing ESPN credentials. Set " + ", ".join(missing) + " in the environment before running a data updater."
        )
    return swid, espn_s2


LEAGUE_KEY = ["Year", "Week", "Team ID"]
PLAYER_MATCHUP_KEY = ["Year", "Week", "Team ID", "Player ID"]

LEAGUE_REQUIRED_COLUMNS = {
    "Year", "Week", "Type", "Team ID", "Points For", "Points Against", "Win", "Loss",
    "Cumulative Points For", "Cumulative Points Against", "Cumulative Wins",
    "Cumulative Losses", "Rank",
}
PLAYER_MATCHUP_REQUIRED_COLUMNS = {
    "Year", "Week", "Team Name", "Team ID", "Player Name", "Player ID", "FPTS",
}


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
