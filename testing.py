import pandas as pd

data = pd.read_csv("basketballBrawlLeagueData.csv")
# Get latest team names for each team ID
team1_id = 16
team2_id = 17
latest_year = data["Year"].max()
latest_year_data = data[data["Year"] == latest_year]
latest_week = latest_year_data["Week"].max()
latest_week_data = latest_year_data[latest_year_data["Week"] == latest_week]
team1_name = latest_week_data[latest_week_data["Team ID"] == team1_id]["Team Name"].iloc[0]
team2_name = latest_week_data[latest_week_data["Team ID"] == team2_id]["Team Name"].iloc[0]

# Filter for matchups between the two teams
h2h_data = data[((data["Team ID"] == team1_id) & (data["Opponent Team ID"] == team2_id))]

print(team1_name)
print(team2_name)
print(h2h_data)
