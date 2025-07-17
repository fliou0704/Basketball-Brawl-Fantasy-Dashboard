from espn_api.basketball import League
import pandas as pd

league_id = 609694684
swid = "{462737C8-F92F-4033-8AD6-1D877AC43C1D}"
espn_s2 = "AEAgnCeltBfv4nKLUgjlax5tsKzVho%2B6cA1L370VKGvF%2B8hlSX4dpV6Gv7kWYNR5t3zCcNNNwmdXlDPD3HMHLCK%2B6EjbZSYRcIKDl32HUTlKJYweuLKQkzjVDaj89PrtCQ6Cv5zujpbZo7SZ50hqICxorzGB3w01Tds62R78b4wQctPA8rL%2ByshLkXQXs9BM8f9ULC5JywoL3i%2B98bHo%2F9JzYyqmCdUvC1ugiM%2F5%2BY63l49PvhdpoEkbn340BC6gShqus0164TuLh28VviKz6JwKssbPorWtoA%2Fx5RhSs%2FLarA%3D%3D"

years = [2023, 2024, 2025]

all_data = pd.DataFrame(columns=["Year", "Week", "Team Name", "Team ID", "Player Name", "Player ID", "FPTS", "Position", "Position2", "Position3", "FTA", "PTS", "3PM", "BLK", "STL", "AST", "REB", "TO", "FGM", "FGA", "FTM"])

for year in years:

    if year == 2023:
        espn_s2 = 'AEB%2BZ33nD3CVjTy1%2BY7Y6lYP5KSTfdAI6lUjIpSJ8WHLUyjlIMjYKiJlolvuDTyLPBjdhVHIE5UlyyOh6M%2BWtfB1WA5v2CtQhc1CVjmoF%2B%2BgYmTNE%2FDJgSUC0ws0N9S%2Bermktd4xrMRGnr6C%2FpE2hqqe%2BSjMMAVw941%2F%2BAqJw5qqPpT4LfO4BQuSGepw20APuVapbRM3uzCzqadS91HCK0%2BTQhEpm1lpVCGlqCx%2F6rb0UwYNqjJeLkbuXXbrkqK9mPrg5QAqGRI914K2U%2Bah2yD08dXZ8xfYB7K0ilPeqJPKJA%3D%3D'
    else:
        espn_s2 = "AEAgnCeltBfv4nKLUgjlax5tsKzVho%2B6cA1L370VKGvF%2B8hlSX4dpV6Gv7kWYNR5t3zCcNNNwmdXlDPD3HMHLCK%2B6EjbZSYRcIKDl32HUTlKJYweuLKQkzjVDaj89PrtCQ6Cv5zujpbZo7SZ50hqICxorzGB3w01Tds62R78b4wQctPA8rL%2ByshLkXQXs9BM8f9ULC5JywoL3i%2B98bHo%2F9JzYyqmCdUvC1ugiM%2F5%2BY63l49PvhdpoEkbn340BC6gShqus0164TuLh28VviKz6JwKssbPorWtoA%2Fx5RhSs%2FLarA%3D%3D"

    league = League(league_id=league_id, year=year, espn_s2=espn_s2, swid=swid)

    df = pd.DataFrame(columns=["Year", "Week", "Team Name", "Team ID", "Player Name", "Player ID", "FPTS", "Position", "Position2", "Position3", "FTA", "PTS", "3PM", "BLK", "STL", "AST", "REB", "TO", "FGM", "FGA", "FTM"])

    eligiblePositions = ['PG', 'SG', 'SF', 'PF', 'C']

    mps = []
    for mp in league.settings.matchup_periods:
        mps.append(mp)
    totalWeeks = int(mps[-1])

    for week in range(1, totalWeeks + 1):
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

    if all_data.empty:
        all_data = df
    else:
        all_data = pd.concat([all_data, df])

all_data.to_csv('data/playerMatchupData.csv', index=False)