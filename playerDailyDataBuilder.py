from espn_api.basketball import League
import pandas as pd

league_id = 609694684
swid = "{462737C8-F92F-4033-8AD6-1D877AC43C1D}"
espn_s2 = "AEAgnCeltBfv4nKLUgjlax5tsKzVho%2B6cA1L370VKGvF%2B8hlSX4dpV6Gv7kWYNR5t3zCcNNNwmdXlDPD3HMHLCK%2B6EjbZSYRcIKDl32HUTlKJYweuLKQkzjVDaj89PrtCQ6Cv5zujpbZo7SZ50hqICxorzGB3w01Tds62R78b4wQctPA8rL%2ByshLkXQXs9BM8f9ULC5JywoL3i%2B98bHo%2F9JzYyqmCdUvC1ugiM%2F5%2BY63l49PvhdpoEkbn340BC6gShqus0164TuLh28VviKz6JwKssbPorWtoA%2Fx5RhSs%2FLarA%3D%3D"

years = [2023, 2024, 2025]

all_data = pd.DataFrame(columns=["Year", "Scoring Period", "Date", "Team Name", "Team ID", "Player Name", "Player ID", "Player Slot", "FPTS"])

for year in years:

    if year == 2023:
        espn_s2 = 'AEB%2BZ33nD3CVjTy1%2BY7Y6lYP5KSTfdAI6lUjIpSJ8WHLUyjlIMjYKiJlolvuDTyLPBjdhVHIE5UlyyOh6M%2BWtfB1WA5v2CtQhc1CVjmoF%2B%2BgYmTNE%2FDJgSUC0ws0N9S%2Bermktd4xrMRGnr6C%2FpE2hqqe%2BSjMMAVw941%2F%2BAqJw5qqPpT4LfO4BQuSGepw20APuVapbRM3uzCzqadS91HCK0%2BTQhEpm1lpVCGlqCx%2F6rb0UwYNqjJeLkbuXXbrkqK9mPrg5QAqGRI914K2U%2Bah2yD08dXZ8xfYB7K0ilPeqJPKJA%3D%3D'
    else:
        espn_s2 = "AEAgnCeltBfv4nKLUgjlax5tsKzVho%2B6cA1L370VKGvF%2B8hlSX4dpV6Gv7kWYNR5t3zCcNNNwmdXlDPD3HMHLCK%2B6EjbZSYRcIKDl32HUTlKJYweuLKQkzjVDaj89PrtCQ6Cv5zujpbZo7SZ50hqICxorzGB3w01Tds62R78b4wQctPA8rL%2ByshLkXQXs9BM8f9ULC5JywoL3i%2B98bHo%2F9JzYyqmCdUvC1ugiM%2F5%2BY63l49PvhdpoEkbn340BC6gShqus0164TuLh28VviKz6JwKssbPorWtoA%2Fx5RhSs%2FLarA%3D%3D"

    league = League(league_id=league_id, year=year, espn_s2=espn_s2, swid=swid)

    scoringPeriods = int(league.scoringPeriodId)

    df = pd.DataFrame(columns=["Year", "Scoring Period", "Date", "Team Name", "Team ID", "Player Name", "Player ID", "Player Slot", "FPTS"])

    for sp in range(1, scoringPeriods + 1):
        for boxScore in league.box_scores(scoring_period=sp, matchup_total=False):

            for player in boxScore.home_lineup:

                played = False
                if bool(player.stats):
                    day_stats = player.stats.get(str(sp))
                    if day_stats and "total" in day_stats:
                        played = True

                if played:
                    date_played = player.stats[str(sp)]["date"]
                    if date_played:
                        date_played = date_played.date()

                    minutes = player.stats[str(sp)]["total"].get("MIN", None)

                    df_row = pd.DataFrame({"Year": [year], "Scoring Period": [sp], "Date":[date_played], "Team Name": [boxScore.home_team.team_name], "Team ID": [boxScore.home_team.team_id], "Player Name": [player.name], "Player ID": [player.playerId], "Player Slot": [player.slot_position], "FPTS": player.points, "MIN": [minutes]})

                    for key, value in player.points_breakdown.items():
                        df_row[key] = [value]

                    if df.empty:
                        df = df_row
                    else:
                        df = pd.concat([df, df_row])

            for player in boxScore.away_lineup:

                played = False
                if bool(player.stats):
                    day_stats = player.stats.get(str(sp))
                    if day_stats and "total" in day_stats:
                        played = True

                if played:
                    date_played = player.stats[str(sp)]["date"]
                    if date_played:
                        date_played = date_played.date()

                    minutes = player.stats[str(sp)]["total"].get("MIN", None)

                    df_row = pd.DataFrame({"Year": [year], "Scoring Period": [sp], "Date":[date_played], "Team Name": [boxScore.away_team.team_name], "Team ID": [boxScore.away_team.team_id], "Player Name": [player.name], "Player ID": [player.playerId], "Player Slot": [player.slot_position], "FPTS": player.points, "MIN": [minutes]})

                    for key, value in player.points_breakdown.items():
                        df_row[key] = [value]

                    if df.empty:
                        df = df_row
                    else:
                        df = pd.concat([df, df_row])

    # Create a mapping from Day (scoring period) to the first known Date
    sp_date_map = df[df["Date"].notna()].groupby("Scoring Period")["Date"].first().to_dict()

    # Apply the map to fill missing dates
    df["Date"] = df.apply(
        lambda row: sp_date_map.get(row["Scoring Period"]) if pd.isna(row["Date"]) else row["Date"],
        axis=1
    )

    # Convert stat columns to numeric
    stat_cols = ["FPTS", "FTA", "PTS", "3PM", "BLK", "STL", "AST", "REB", "TO", "FGM", "FGA", "FTM"]
    for col in stat_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col])

    if all_data.empty:
        all_data = df
    else:
        all_data = pd.concat([all_data, df], ignore_index=True)

all_data.to_csv('data/playerDailyData.csv', index=False)