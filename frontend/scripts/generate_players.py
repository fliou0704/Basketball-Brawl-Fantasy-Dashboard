"""Export player search records and ESPN-ID-keyed Basketball Brawl careers."""

from __future__ import annotations

import argparse
from itertools import groupby
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from build_homepage import logo_config, team_info, write_json
from playerDailyAggregation import DAILY_STATS, credited_daily_rows, load_season_metadata

STAT_DIVISORS = {"FGM": 2, "FGA": -1, "FTA": -1, "AST": 2, "STL": 4, "BLK": 4, "TO": -2}
STAT_KEYS = ("FPTS", "PTS", "REB", "AST", "STL", "BLK", "3PM", "TO", "FGM", "FGA", "FTM", "FTA")
ACTIVE_OWNERSHIP_ACTIONS = {"DRAFTED", "KEEPER", "WAIVER ADDED", "FA ADDED", "RECEIVED"}


def number(value):
    value = float(value)
    return int(value) if value.is_integer() else round(value, 2)


def latest_eligibility(daily: pd.DataFrame) -> dict[int, list[str]]:
    """Use the latest saved ESPN fantasy eligibility for each player."""
    rows = daily.sort_values(["Year", "Scoring Period", "Date"], kind="stable").drop_duplicates("Player ID", keep="last")
    return {
        int(row["Player ID"]): [row[column] for column in ("Position", "Position2", "Position3") if pd.notna(row[column])]
        for _, row in rows.iterrows()
    }


def current_ownership(activity: pd.DataFrame, team_lookup: dict[int, dict]) -> dict[int, dict]:
    """Resolve the latest-season roster state from the canonical activity ledger."""
    rows = activity[pd.notna(activity["Player ID"])].copy()
    rows = rows[rows["Year"] == rows["Year"].max()]
    rows["_order"] = range(len(rows))
    rows = rows.sort_values(["Date", "Time", "_order"], kind="stable").drop_duplicates("Player ID", keep="last")
    return {
        int(row["Player ID"]): team_lookup[int(row["Team ID"])]
        for _, row in rows.iterrows()
        if row["Action"] in ACTIVE_OWNERSHIP_ACTIONS
    }


def search_record(player_id, row, eligibility, fantasy_team):
    clean = lambda value: None if pd.isna(value) else value
    return {
        "playerId": int(player_id), "name": row["Full Name"], "headshot": clean(row.get("Headshot URL")),
        "position": clean(row.get("NBA Position Abbreviation")), "nbaTeam": clean(row.get("NBA Team Name")),
        "active": bool(row.get("Active")), "fantasyEligibility": eligibility, "fantasyTeam": fantasy_team,
    }


def summary(totals, starts, **extra):
    minutes = float(totals.get("MIN", 0))
    fpts = float(totals.get("FPTS", 0))
    return {
        **extra, "starts": int(starts), "MIN": number(minutes),
        **{key: number(totals.get(key, 0)) for key in STAT_KEYS},
        "fpPerStart": round(fpts / starts, 2) if starts else None,
        "mpg": round(minutes / starts, 2) if starts else None,
        "fppm": round(fpts / minutes, 2) if minutes else None,
    }


def aggregate_career(daily: pd.DataFrame, team_lookup: dict[int, dict]) -> tuple[list[dict], dict]:
    if daily.empty:
        return [], summary({}, 0, rowType="career")
    rows = daily.copy()
    for stat, divisor in STAT_DIVISORS.items():
        if stat in rows:
            rows[stat] = rows[stat] / divisor
    rows["Date"] = pd.to_datetime(rows["Date"], errors="raise")
    order = [column for column in ("Year", "Scoring Period", "Date") if column in rows.columns]
    rows = rows.sort_values(order, kind="stable")
    rows["Stint"] = rows.groupby("Year")["Team ID"].transform(lambda teams: teams.ne(teams.shift()).cumsum())
    groups = []
    for (year, _, team_id), stint in rows.groupby(["Year", "Stint", "Team ID"], sort=False):
        totals = stint[[*STAT_KEYS, "MIN"]].sum()
        groups.append(summary(totals, len(stint),
            rowType="stint", season=int(year), team=team_lookup[int(team_id)],
            firstDate=stint["Date"].min().date().isoformat(), lastDate=stint["Date"].max().date().isoformat(),
        ))
    groups.sort(key=lambda row: (row["season"], row["firstDate"], row["lastDate"], row["team"]["teamId"]))
    display_rows = []
    for year, stints in groupby(groups, key=lambda row: row["season"]):
        season_stints = list(stints)
        display_rows.extend(season_stints)
        if len(season_stints) > 1:
            season_rows = rows[rows["Year"] == year]
            display_rows.append(summary(season_rows[[*STAT_KEYS, "MIN"]].sum(), len(season_rows), rowType="seasonTotal", season=int(year)))
    career = summary(rows[[*STAT_KEYS, "MIN"]].sum(), len(rows), rowType="career")
    return display_rows, career


def build(source: Path, output: Path) -> dict:
    metadata = pd.read_csv(source / "playerMetadata.csv").set_index("ESPN Player ID")
    daily = pd.read_csv(source / "playerDailyData.csv")
    credited = credited_daily_rows(daily, load_season_metadata())
    league = pd.read_csv(source / "basketballBrawlLeagueData.csv")
    config = logo_config()
    team_rows = league.sort_values(["Year", "Week"]).drop_duplicates("Team ID", keep="last")
    teams = {int(row["Team ID"]): team_info(row, config) for _, row in team_rows.iterrows()}
    eligibility = latest_eligibility(daily)
    ownership = current_ownership(pd.read_csv(source / "activityData.csv"), teams)
    players = []
    for player_id, row in metadata.sort_values("Full Name").iterrows():
        player_eligibility = eligibility.get(int(player_id), [])
        fantasy_team = ownership.get(int(player_id))
        record = search_record(player_id, row, player_eligibility, fantasy_team)
        players.append(record)
        career_rows, career = aggregate_career(credited[credited["Player ID"] == player_id], teams)
        write_json(output / "players" / f"{int(player_id)}.json", {
            "schemaVersion": 1, "playerId": int(player_id), "fantasyEligibility": player_eligibility,
            "fantasyTeam": fantasy_team, "careerRows": career_rows, "career": career,
        })
    payload = {"schemaVersion": 1, "players": players}
    write_json(output / "players.json", payload)
    print(f"Players: {len(players)} profiles, {len(credited)} credited starts")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "frontend/public/data")
    args = parser.parse_args()
    build(args.source_dir, args.output_dir)
