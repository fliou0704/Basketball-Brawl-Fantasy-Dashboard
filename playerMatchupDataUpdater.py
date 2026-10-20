from espn_api.basketball import League
import pandas as pd
from datetime import datetime
import numpy as np
from dataUpdateSafety import (
    PLAYER_MATCHUP_KEY,
    atomic_write_csv,
    merge_incremental_rows,
    require_espn_credentials,
    validate_player_matchup_data,
)


PLAYER_MATCHUP_DATA_PATH = "data/playerMatchupData.csv"


def prepare_player_matchup_update(existing_data, new_rows):
    """Build a validated, append-only player-matchup candidate without writing it."""
    return merge_incremental_rows(
        existing_data,
        new_rows,
        PLAYER_MATCHUP_KEY,
        validate_player_matchup_data,
    )


def write_player_matchup_update(existing_data, new_rows, destination=PLAYER_MATCHUP_DATA_PATH):
    """Validate before atomically replacing the CSV; return whether a write occurred."""
    candidate = prepare_player_matchup_update(existing_data, new_rows)
    if candidate.equals(existing_data):
        return False
    atomic_write_csv(candidate, destination)
    return True

def update_playerMatchup_data(data_path=PLAYER_MATCHUP_DATA_PATH, active_year=None, league_factory=League, refresh_from_by_year=None):
    League = league_factory
    league_id = 609694684
    swid, espn_s2 = require_espn_credentials()

    current_year = datetime.now().year
    current_year = active_year or current_year + 1
    leagueYear = current_year
    try:
        league = League(league_id=league_id, year=leagueYear, espn_s2=espn_s2, swid=swid)
    except Exception as e:
        year = leagueYear - 1
        league = League(league_id=league_id, year=year, espn_s2=espn_s2, swid=swid)
        leagueYear = year

    data = pd.read_csv(data_path)
    original = data.copy(deep=True)
    for year, first_week in (refresh_from_by_year or {}).items():
        data = data[~((data['Year'] == year) & (data['Week'] >= first_week))].copy()

    maxyear = data["Year"].max()
    maxweek = data[data["Year"] == maxyear]["Week"].max()

    yearsToUpdate = []

    if (maxyear != leagueYear):
        league = League(league_id=league_id, year=maxyear, espn_s2=espn_s2, swid=swid)
        if (maxweek != len(league.settings.matchup_periods)):
            yearsToUpdate.append(maxyear)
        year = maxyear
        while(year != leagueYear):
            year += 1
            yearsToUpdate.append(year)
    else:
        league = League(league_id=league_id, year=maxyear, espn_s2=espn_s2, swid=swid)
        if (maxweek != league.currentMatchupPeriod - 1):
            if (league.currentMatchupPeriod == len(league.settings.matchup_periods)):
                if (league.scoreboard(league.currentMatchupPeriod)[0].winner != "UNDECIDED"):
                    if (maxweek != league.currentMatchupPeriod):
                        yearsToUpdate.append(maxyear)
            else:    
                yearsToUpdate.append(maxyear)

    new_data_frames = []

    for year in yearsToUpdate:

        swid, espn_s2 = require_espn_credentials()

        league = League(league_id=league_id, year=year, espn_s2=espn_s2, swid=swid)
        regularWeeks = league.settings.reg_season_count
        totalWeeks = len(league.settings.matchup_periods)
        startingWeek = 1
        if not (data[data["Year"] == year].empty):
            startingWeek = data[data["Year"] == year]["Week"].max() + 1
        #print(year)
        #print(leagueYear)
        endingWeek = league.currentMatchupPeriod
        if (endingWeek == totalWeeks):
            if (league.scoreboard(endingWeek)[0].winner != "UNDECIDED"):
                endingWeek = endingWeek + 1

        df = pd.DataFrame(columns=["Year", "Week", "Team Name", "Team ID", "Player Name", "Player ID", "FPTS", "Position", "Position2", "Position3", "FTA", "PTS", "3PM", "BLK", "STL", "AST", "REB", "TO", "FGM", "FGA", "FTM"])
        if startingWeek != 1:
                df = data[data["Year"] == year]

        eligiblePositions = ['PG', 'SG', 'SF', 'PF', 'C']

        for week in range(startingWeek, endingWeek):
            for boxScore in league.box_scores(week):
                for player in boxScore.home_lineup:
                    df_row = pd.DataFrame({"Year": [year], "Week": [week], "Team Name": [boxScore.home_team.team_name], "Team ID": [boxScore.home_team.team_id],  "Player Name": [player.name], "Player ID": [player.playerId], "FPTS": player.points, "Position": None, "Position2": None, "Position3": None})
                    positionPriority = 0

                    for position in player.eligibleSlots:
                        positionPriority += 1
                        if positionPriority == 1:
                            df_row["Position"] = [position]
                        elif position in eligiblePositions:
                            if positionPriority == 2:
                                df_row["Position2"] = [position]
                            else:
                                df_row["Position3"] = [position]
                        else:
                            break

                    for key, value in player.points_breakdown.items():
                        df_row[key] = [value]

                    if df.empty:
                        df = df_row
                    else:
                        df = pd.concat([df, df_row])

                for player in boxScore.away_lineup:
                    df_row = pd.DataFrame({"Year": [year], "Week": [week], "Team Name": [boxScore.away_team.team_name], "Team ID": [boxScore.away_team.team_id], "Player Name": [player.name], "Player ID": [player.playerId], "FPTS": player.points, "Position": None, "Position2": None, "Position3": None})
                    positionPriority = 0

                    for position in player.eligibleSlots:
                        positionPriority += 1
                        if positionPriority == 1:
                            df_row["Position"] = [position]
                        elif position in eligiblePositions:
                            if positionPriority == 2:
                                df_row["Position2"] = [position]
                            else:
                                df_row["Position3"] = [position]
                        else:
                            break

                    for key, value in player.points_breakdown.items():
                        df_row[key] = [value]

                    if df.empty:
                        df = df_row
                    else:
                        df = pd.concat([df, df_row])

        # Convert stat columns to numeric
        stat_cols = ["FPTS", "FTA", "PTS", "3PM", "BLK", "STL", "AST", "REB", "TO", "FGM", "FGA", "FTM"]
        for col in stat_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col])

        # Keep already stored weeks untouched; only append rows that were fetched
        # for a week after the persisted maximum.
        new_data_frames.append(df[df["Week"] >= startingWeek].copy())

    if not new_data_frames:
        return False
    new_rows = pd.concat(new_data_frames, ignore_index=True)
    if refresh_from_by_year:
        from nearLiveSafety import replace_partitions
        partitions = {(int(y), int(w)) for y, w in original[['Year', 'Week']].itertuples(index=False, name=None)
                      if y in refresh_from_by_year and w >= refresh_from_by_year[y]}
        stored_partitions = set(original[['Year', 'Week']].itertuples(index=False, name=None))
        partitions.update(set(new_rows[['Year', 'Week']].itertuples(index=False, name=None)) - stored_partitions)
        candidate = replace_partitions(original, new_rows, partitions, 'Week', PLAYER_MATCHUP_KEY, validate_player_matchup_data)
        if candidate.equals(original):
            return False
        atomic_write_csv(candidate, data_path)
        return True
    return write_player_matchup_update(data, new_rows, destination=data_path)

if __name__ == "__main__":
    update_playerMatchup_data()
