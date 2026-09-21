"""Incremental, validated updates for the dashboard's daily-player dataset."""

from datetime import datetime

import pandas as pd
from espn_api.basketball import League

from dataUpdateSafety import (
    PLAYER_DAILY_KEY,
    atomic_write_csv,
    merge_refreshable_daily_rows,
    require_espn_credentials,
    validate_player_daily_data,
)
from playerDailyAggregation import eligible_position_fields


PLAYER_DAILY_DATA_PATH = "data/playerDailyData.csv"
DAILY_STAT_COLUMNS = ["FPTS", "MIN", "FTA", "PTS", "3PM", "BLK", "STL", "AST", "REB", "TO", "FGM", "FGA", "FTM"]


def available_scoring_period(league):
    """Return the latest ESPN period that belongs to the fantasy season."""
    return min(int(league.scoringPeriodId), int(league.finalScoringPeriod))


def prepare_player_daily_update(existing_data, fetched_rows, terminal_period_by_year=None, refresh_period_by_year=None):
    """Build a validated daily candidate with an optional latest-period refresh."""
    refresh_period_by_year = refresh_period_by_year or {}
    if refresh_period_by_year:
        return merge_refreshable_daily_rows(
            existing_data,
            fetched_rows,
            refresh_period_by_year,
            terminal_period_by_year,
        )
    # Used for a first-ever season import: no stored period exists to refresh.
    from dataUpdateSafety import merge_incremental_rows
    return merge_incremental_rows(
        existing_data,
        fetched_rows,
        PLAYER_DAILY_KEY,
        validate_player_daily_data,
        terminal_period_by_year,
    )


def write_player_daily_update(existing_data, fetched_rows, destination=PLAYER_DAILY_DATA_PATH, terminal_period_by_year=None, refresh_period_by_year=None):
    """Validate first, then atomically replace the CSV only when records changed."""
    candidate = prepare_player_daily_update(
        existing_data,
        fetched_rows,
        terminal_period_by_year,
        refresh_period_by_year,
    )
    if candidate.equals(existing_data):
        return False
    atomic_write_csv(candidate, destination)
    return True


def _record_for_player(year, scoring_period, team, player):
    """Normalize one ESPN lineup player into the existing daily CSV schema."""
    day_stats = player.stats.get(str(scoring_period)) if player.stats else None
    if not day_stats or "total" not in day_stats:
        return None
    date_played = day_stats.get("date")
    date_played = date_played.date().isoformat() if date_played else None
    record = {
        "Year": year,
        "Scoring Period": scoring_period,
        "Date": date_played,
        "Team Name": team.team_name,
        "Team ID": team.team_id,
        "Player Name": player.name,
        "Player ID": player.playerId,
        "Player Slot": player.slot_position,
        "FPTS": player.points,
        "MIN": day_stats["total"].get("MIN"),
    }
    record.update(eligible_position_fields(player.eligibleSlots))
    record.update(player.points_breakdown)
    return record


def fetch_daily_rows(league, year, start_period, end_period, columns):
    """Fetch only an inclusive missing scoring-period range from a supplied league."""
    records = []
    for scoring_period in range(start_period, end_period + 1):
        for box_score in league.box_scores(scoring_period=scoring_period, matchup_total=False):
            for player in box_score.home_lineup:
                record = _record_for_player(year, scoring_period, box_score.home_team, player)
                if record:
                    records.append(record)
            for player in box_score.away_lineup:
                record = _record_for_player(year, scoring_period, box_score.away_team, player)
                if record:
                    records.append(record)

    rows = pd.DataFrame(records, columns=columns)
    if rows.empty:
        return rows
    period_dates = rows.dropna(subset=["Date"]).groupby("Scoring Period")["Date"].first()
    rows["Date"] = rows["Date"].fillna(rows["Scoring Period"].map(period_dates))
    for column in DAILY_STAT_COLUMNS:
        rows[column] = pd.to_numeric(rows[column], errors="coerce")
    return rows


def update_player_daily_data():
    """Refresh the latest stored period and append any later daily periods."""
    league_id = 609694684
    swid, espn_s2 = require_espn_credentials()
    requested_year = datetime.now().year + 1
    try:
        active_league = League(league_id=league_id, year=requested_year, espn_s2=espn_s2, swid=swid)
        active_year = requested_year
    except Exception:
        active_year = requested_year - 1
        swid, espn_s2 = require_espn_credentials()
        active_league = League(league_id=league_id, year=active_year, espn_s2=espn_s2, swid=swid)

    existing_data = pd.read_csv(PLAYER_DAILY_DATA_PATH)
    max_year = int(existing_data["Year"].max())
    max_period = int(existing_data.loc[existing_data["Year"] == max_year, "Scoring Period"].max())
    terminal_period_by_year = {}
    years_to_update = []
    refresh_period_by_year = {}

    if max_year != active_year:
        swid, espn_s2 = require_espn_credentials()
        prior_league = League(league_id=league_id, year=max_year, espn_s2=espn_s2, swid=swid)
        prior_terminal_period = available_scoring_period(prior_league)
        terminal_period_by_year[max_year] = prior_terminal_period
        years_to_update.append(max_year)
        refresh_period_by_year[max_year] = max_period
        years_to_update.extend(range(max_year + 1, active_year + 1))
    else:
        years_to_update.append(active_year)
        refresh_period_by_year[active_year] = max_period

    new_data_frames = []
    for year in years_to_update:
        swid, espn_s2 = require_espn_credentials()
        league = active_league if year == active_year else League(
            league_id=league_id, year=year, espn_s2=espn_s2, swid=swid
        )
        terminal_period = available_scoring_period(league)
        terminal_period_by_year[year] = terminal_period
        existing_year = existing_data[existing_data["Year"] == year]
        # Re-fetch the last stored period. It may still be in progress; periods
        # after it are new and will be appended by the merge boundary.
        start_period = 1 if existing_year.empty else int(existing_year["Scoring Period"].max())
        new_data_frames.append(fetch_daily_rows(league, year, start_period, terminal_period, existing_data.columns.tolist()))

    if not new_data_frames:
        return False
    new_rows = pd.concat(new_data_frames, ignore_index=True)
    return write_player_daily_update(
        existing_data,
        new_rows,
        terminal_period_by_year=terminal_period_by_year,
        refresh_period_by_year=refresh_period_by_year,
    )


if __name__ == "__main__":
    update_player_daily_data()
