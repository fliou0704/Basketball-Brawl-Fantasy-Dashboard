"""Export player search records and ESPN-ID-keyed Basketball Brawl careers."""

from __future__ import annotations

import argparse
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


def number(value):
    value = float(value)
    return int(value) if value.is_integer() else round(value, 2)


def search_record(player_id, row):
    clean = lambda value: None if pd.isna(value) else value
    return {
        "playerId": int(player_id), "name": row["Full Name"], "headshot": clean(row.get("Headshot URL")),
        "position": clean(row.get("NBA Position Abbreviation")), "nbaTeam": clean(row.get("NBA Team Name")),
        "active": bool(row.get("Active")),
    }


def aggregate_career(daily: pd.DataFrame, team_lookup: dict[int, dict]) -> tuple[list[dict], dict]:
    if daily.empty:
        return [], {"starts": 0, **{key: 0 for key in STAT_KEYS}}
    rows = daily.copy()
    for stat, divisor in STAT_DIVISORS.items():
        if stat in rows:
            rows[stat] = rows[stat] / divisor
    rows["Date"] = pd.to_datetime(rows["Date"], errors="raise")
    order = [column for column in ("Year", "Date", "Scoring Period") if column in rows.columns]
    rows = rows.sort_values(order, kind="stable")
    rows["Stint"] = rows.groupby("Year")["Team ID"].transform(lambda teams: teams.ne(teams.shift()).cumsum())
    groups = []
    for (year, _, team_id), stint in rows.groupby(["Year", "Stint", "Team ID"], sort=False):
        totals = stint[list(STAT_KEYS)].sum()
        groups.append({
            "season": int(year), "team": team_lookup[int(team_id)],
            "firstDate": stint["Date"].min().date().isoformat(), "lastDate": stint["Date"].max().date().isoformat(),
            "starts": int(len(stint)), **{key: number(totals[key]) for key in STAT_KEYS},
        })
    groups.sort(key=lambda row: (row["season"], row["firstDate"], row["lastDate"], row["team"]["teamId"]))
    totals = rows[list(STAT_KEYS)].sum()
    career = {"starts": int(len(rows)), **{key: number(totals[key]) for key in STAT_KEYS}}
    return groups, career


def build(source: Path, output: Path) -> dict:
    metadata = pd.read_csv(source / "playerMetadata.csv").set_index("ESPN Player ID")
    daily = pd.read_csv(source / "playerDailyData.csv")
    credited = credited_daily_rows(daily, load_season_metadata())
    league = pd.read_csv(source / "basketballBrawlLeagueData.csv")
    config = logo_config()
    team_rows = league.sort_values(["Year", "Week"]).drop_duplicates("Team ID", keep="last")
    teams = {int(row["Team ID"]): team_info(row, config) for _, row in team_rows.iterrows()}
    players = []
    for player_id, row in metadata.sort_values("Full Name").iterrows():
        record = search_record(player_id, row)
        players.append(record)
        career_rows, career = aggregate_career(credited[credited["Player ID"] == player_id], teams)
        write_json(output / "players" / f"{int(player_id)}.json", {
            "schemaVersion": 1, "playerId": int(player_id), "careerRows": career_rows, "career": career,
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
