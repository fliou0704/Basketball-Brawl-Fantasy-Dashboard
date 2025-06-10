from espn_api.basketball import League
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt
import seaborn as sns

### TODO
### - Historical data, head-to-head record against every team with matchup data including players and points breakdown
### - Playoff stats




### espn_s2 for 2021-2023
# espn_s2 = 'AEB%2BZ33nD3CVjTy1%2BY7Y6lYP5KSTfdAI6lUjIpSJ8WHLUyjlIMjYKiJlolvuDTyLPBjdhVHIE5UlyyOh6M%2BWtfB1WA5v2CtQhc1CVjmoF%2B%2BgYmTNE%2FDJgSUC0ws0N9S%2Bermktd4xrMRGnr6C%2FpE2hqqe%2BSjMMAVw941%2F%2BAqJw5qqPpT4LfO4BQuSGepw20APuVapbRM3uzCzqadS91HCK0%2BTQhEpm1lpVCGlqCx%2F6rb0UwYNqjJeLkbuXXbrkqK9mPrg5QAqGRI914K2U%2Bah2yD08dXZ8xfYB7K0ilPeqJPKJA%3D%3D'

league_id = 609694684
swid = "{462737C8-F92F-4033-8AD6-1D877AC43C1D}"
years = [2021, 2022, 2023, 2024]

df = pd.DataFrame(columns=["Year", "Week", "Type", "Team Name", "Home/Away", "Points For", "Points Against", "Win", "Loss", "Opponent Team Name"])

for year in years:

    df_year = pd.DataFrame(columns=["Year", "Week", "Type", "Team Name", "Home/Away", "Points For", "Points Against", "Win", "Loss", "Opponent Team Name"])

    espn_s2 = ''
    if year in [2021, 2022, 2023]: ### espn_s2 for 2021-2023
        espn_s2 = 'AEB%2BZ33nD3CVjTy1%2BY7Y6lYP5KSTfdAI6lUjIpSJ8WHLUyjlIMjYKiJlolvuDTyLPBjdhVHIE5UlyyOh6M%2BWtfB1WA5v2CtQhc1CVjmoF%2B%2BgYmTNE%2FDJgSUC0ws0N9S%2Bermktd4xrMRGnr6C%2FpE2hqqe%2BSjMMAVw941%2F%2BAqJw5qqPpT4LfO4BQuSGepw20APuVapbRM3uzCzqadS91HCK0%2BTQhEpm1lpVCGlqCx%2F6rb0UwYNqjJeLkbuXXbrkqK9mPrg5QAqGRI914K2U%2Bah2yD08dXZ8xfYB7K0ilPeqJPKJA%3D%3D'
    else: ### espn_s2 for 2024
        espn_s2 = 'AEAgnCeltBfv4nKLUgjlax5tsKzVho%2B6cA1L370VKGvF%2B8hlSX4dpV6Gv7kWYNR5t3zCcNNNwmdXlDPD3HMHLCK%2B6EjbZSYRcIKDl32HUTlKJYweuLKQkzjVDaj89PrtCQ6Cv5zujpbZo7SZ50hqICxorzGB3w01Tds62R78b4wQctPA8rL%2ByshLkXQXs9BM8f9ULC5JywoL3i%2B98bHo%2F9JzYyqmCdUvC1ugiM%2F5%2BY63l49PvhdpoEkbn340BC6gShqus0164TuLh28VviKz6JwKssbPorWtoA%2Fx5RhSs%2FLarA%3D%3D'

    league = League(league_id=league_id, year=year, espn_s2=espn_s2, swid=swid)

    for team in league.teams:
        # df_row = [year, week, type, team_name, home/away, points for, points against, win, loss, opponenet team_name]
        week = 0
        for matchup in team.schedule:
            week += 1
            type = "Regular"
            if year == 2021 and week > 16:
                type = "Playoffs"
            if year in [2022, 2023] and week > 21:
                type = "Playoffs"
            if year == 2024 and week > 20:
                type = "Playoffs"
            df_row = pd.DataFrame({"Year": [year], "Week": [week], "Type": [type], "Team Name": [team.team_name]})
            place = ""
            result = ""
            if matchup.home_team.team_name == team.team_name:
                place = "HOME"
                df_row["Home/Away"] = ["Home"]
                df_row["Points For"] = [matchup.home_final_score]
                df_row["Points Against"] = [matchup.away_final_score]
                if matchup.winner == place:
                    result = "W"
                    df_row["Win"] = [1]
                    df_row["Loss"] = [0]
                else:
                    result = "L"
                    df_row["Win"] = [0]
                    df_row["Loss"] = [1]
                df_row["Opponent Team Name"] = [matchup.away_team.team_name]
                #print(matchup.home_team.team_name, matchup.home_final_score, matchup.away_team.team_name, matchup.away_final_score, place, result)
            else:
                place = "AWAY"
                df_row["Home/Away"] = ["Away"]
                df_row["Points For"] = [matchup.away_final_score]
                df_row["Points Against"] = [matchup.home_final_score]
                if matchup.winner == place:
                    result = "W"
                    df_row["Win"] = [1]
                    df_row["Loss"] = [0]
                else:
                    result = "L"
                    df_row["Win"] = [0]
                    df_row["Loss"] = [1]
                df_row["Opponent Team Name"] = [matchup.home_team.team_name]
                #print(matchup.away_team.team_name, matchup.away_final_score, matchup.home_team.team_name, matchup.home_final_score, place, result)
            df_year = pd.concat([df_year, df_row])

    df = pd.concat([df, df_year])
#print(df)

# Step 1: Calculate Head-to-Head Records
head_to_head = df.groupby(['Team Name', 'Opponent Team Name', 'Type']).agg(
    wins=('Win', 'sum'),
    losses=('Loss', 'sum')
).reset_index()

# Step 2: Create Summary DataFrame for Visualization
# This is an example for regular season only. Repeat similarly for playoffs and total.
regular_season = head_to_head[head_to_head['Type'] == 'Regular']
pivot_regular = regular_season.pivot('Team Name', 'Opponent Team Name', 'wins')  # Show wins as a sample metric

print(pivot_regular.dtypes)
pivot_regular = pivot_regular.fillna(0)
pivot_regular = pivot_regular.astype(float)

# Step 3: Visualization
plt.figure(figsize=(10, 8))
sns.heatmap(pivot_regular, annot=True, cmap='coolwarm', linewidths=0.5)
plt.title('Head-to-Head Wins (Regular Season)')
plt.show()
