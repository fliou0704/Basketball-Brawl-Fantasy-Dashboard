"""Shared player-daily enrichment and matchup-week aggregation helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from dataUpdateSafety import DataValidationError


ROOT = Path(__file__).resolve().parent
SCORING_PERIOD_MAP_PATH = ROOT / "data" / "scoringPeriodMatchupMap.csv"
SEASON_METADATA_PATH = ROOT / "frontend" / "source" / "season-metadata.json"

NBA_POSITIONS = ("PG", "SG", "SF", "PF", "C")
POSITION_COLUMNS = ("Position", "Position2", "Position3")
DAILY_STATS = ("FPTS", "FTA", "PTS", "3PM", "BLK", "STL", "AST", "REB", "TO", "FGM", "FGA", "FTM")
DAILY_KEY = ("Year", "Scoring Period", "Team ID", "Player ID")
WEEKLY_KEY = ("Year", "Week", "Team ID", "Player ID")


def eligible_position_values(eligible_slots) -> list[str]:
    """Keep ESPN's ordered real-position eligibility and reject silent truncation."""
    positions = [slot for slot in eligible_slots if slot in NBA_POSITIONS]
    positions = list(dict.fromkeys(positions))
    if len(positions) > len(POSITION_COLUMNS):
        raise DataValidationError(
            f"ESPN returned {len(positions)} real positions; the daily schema supports only three"
        )
    return positions


def eligible_position_fields(eligible_slots) -> dict[str, str | None]:
    positions = eligible_position_values(eligible_slots)
    return {
        column: positions[index] if index < len(positions) else None
        for index, column in enumerate(POSITION_COLUMNS)
    }


def build_scoring_period_map(metadata: dict) -> pd.DataFrame:
    """Expand saved ESPN matchup-period boundaries into one explicit row per period."""
    rows = []
    for season in metadata["seasons"]:
        year = int(season["season"])
        for week in season["weeks"]:
            rows.extend(
                {
                    "Year": year,
                    "Scoring Period": scoring_period,
                    "Week": int(week["week"]),
                }
                for scoring_period in range(int(week["firstPeriod"]), int(week["lastPeriod"]) + 1)
            )
    result = pd.DataFrame(rows, columns=["Year", "Scoring Period", "Week"])
    validate_scoring_period_map(result)
    return result


def load_season_metadata(path: Path = SEASON_METADATA_PATH) -> dict:
    with path.open() as handle:
        return json.load(handle)


def load_scoring_period_map(path: Path = SCORING_PERIOD_MAP_PATH) -> pd.DataFrame:
    mapping = pd.read_csv(path)
    validate_scoring_period_map(mapping)
    return mapping


def validate_scoring_period_map(mapping: pd.DataFrame, daily: pd.DataFrame | None = None) -> None:
    required = {"Year", "Scoring Period", "Week"}
    if not required.issubset(mapping.columns):
        raise DataValidationError(f"scoring-period map is missing columns: {sorted(required - set(mapping.columns))}")
    if mapping.duplicated(["Year", "Scoring Period"]).any():
        raise DataValidationError("scoring-period map contains duplicate Year + Scoring Period rows")
    for column in required:
        values = pd.to_numeric(mapping[column], errors="coerce")
        if values.isna().any() or (values < 1).any() or not values.map(lambda value: float(value).is_integer()).all():
            raise DataValidationError(f"scoring-period map contains invalid {column}")
    if daily is not None:
        periods = daily[["Year", "Scoring Period"]].drop_duplicates()
        coverage = periods.merge(mapping[["Year", "Scoring Period"]], how="left", indicator=True)
        if (coverage["_merge"] != "both").any():
            missing = coverage.loc[coverage["_merge"] != "both", ["Year", "Scoring Period"]].head(3)
            raise DataValidationError(f"daily scoring periods are missing matchup weeks: {missing.to_dict('records')}")


def active_slots_by_year(metadata: dict) -> dict[int, set[str]]:
    return {int(season["season"]): set(season["lineupSlots"]) for season in metadata["seasons"]}


def attach_matchup_weeks(daily: pd.DataFrame, mapping: pd.DataFrame) -> pd.DataFrame:
    validate_scoring_period_map(mapping, daily)
    result = daily.merge(mapping, on=["Year", "Scoring Period"], how="left", validate="many_to_one")
    if len(result) != len(daily):
        raise DataValidationError("attaching matchup weeks changed the daily row count")
    return result


def credited_daily_rows(daily: pd.DataFrame, season_metadata: dict) -> pd.DataFrame:
    """Return played games credited to an active fantasy lineup slot."""
    rows = daily.copy()
    active_by_year = active_slots_by_year(season_metadata)
    active = [
        slot in active_by_year.get(int(year), set())
        for year, slot in zip(rows["Year"], rows["Player Slot"])
    ]
    minutes = pd.to_numeric(rows["MIN"], errors="coerce").fillna(0)
    return rows[pd.Series(active, index=rows.index) & (minutes > 0)].copy()


def aggregate_daily_to_weekly(
    daily: pd.DataFrame,
    mapping: pd.DataFrame,
    season_metadata: dict,
    *,
    active_only: bool = True,
) -> pd.DataFrame:
    """Aggregate daily performance while preserving credited-vs-bench semantics."""
    rows = attach_matchup_weeks(daily, mapping)
    active_by_year = active_slots_by_year(season_metadata)
    rows["Active"] = [
        slot in active_by_year.get(int(year), set())
        for year, slot in zip(rows["Year"], rows["Player Slot"])
    ]
    if active_only:
        rows = rows[rows["Active"]].copy()

    aggregations = {column: "sum" for column in DAILY_STATS if column in rows.columns}
    aggregations.update({"MIN": "sum", "Team Name": "last", "Player Name": "last"})
    weekly = rows.groupby(list(WEEKLY_KEY), as_index=False).agg(aggregations)
    games = rows.groupby(list(WEEKLY_KEY)).size().rename("GP")
    starts = rows[rows["Active"]].groupby(list(WEEKLY_KEY)).size().rename("Fantasy Starts")
    weekly = weekly.merge(games, on=list(WEEKLY_KEY), how="left").merge(
        starts, on=list(WEEKLY_KEY), how="left"
    )
    weekly["Fantasy Starts"] = weekly["Fantasy Starts"].fillna(0).astype(int)
    weekly["FPPM"] = weekly["FPTS"] / weekly["MIN"].replace(0, pd.NA)
    weekly["Fantasy Points per Start"] = weekly["FPTS"] / weekly["Fantasy Starts"].replace(0, pd.NA)
    return weekly
