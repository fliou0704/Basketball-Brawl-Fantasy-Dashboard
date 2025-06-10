from espn_api.basketball import League
import pandas as pd
from datetime import datetime
import time

### TODO
### - Look into merging player dataset with basketball reference dataset to compare fantasy points and win share
### - Look into merging player dataset with another player dataset to show unique stats about teams like height, weight, birhtplace, etc. 
### - Look into adding images to player dataset somehow
### - Spruce up visuals in fantasyPlayerVisuals.py
### - Python version of Tableau visuals
### - Similar to fantasyIdealLineup.py but year long fant All-NBA team
### - Showcase luckiest and most unlucky teams 
### - Playoff stats
### - Rank teams based on average position rank? Might not show anything special.
### - Create a dataset for league activity
### - Last week in review with team of the week, matchup of the week, highest scorers of week, etc




### espn_s2 for 2021-2023
# espn_s2 = 'AEB%2BZ33nD3CVjTy1%2BY7Y6lYP5KSTfdAI6lUjIpSJ8WHLUyjlIMjYKiJlolvuDTyLPBjdhVHIE5UlyyOh6M%2BWtfB1WA5v2CtQhc1CVjmoF%2B%2BgYmTNE%2FDJgSUC0ws0N9S%2Bermktd4xrMRGnr6C%2FpE2hqqe%2BSjMMAVw941%2F%2BAqJw5qqPpT4LfO4BQuSGepw20APuVapbRM3uzCzqadS91HCK0%2BTQhEpm1lpVCGlqCx%2F6rb0UwYNqjJeLkbuXXbrkqK9mPrg5QAqGRI914K2U%2Bah2yD08dXZ8xfYB7K0ilPeqJPKJA%3D%3D'

league_id = 609694684
swid = "{462737C8-F92F-4033-8AD6-1D877AC43C1D}"
espn_s2 = 'AEAgnCeltBfv4nKLUgjlax5tsKzVho%2B6cA1L370VKGvF%2B8hlSX4dpV6Gv7kWYNR5t3zCcNNNwmdXlDPD3HMHLCK%2B6EjbZSYRcIKDl32HUTlKJYweuLKQkzjVDaj89PrtCQ6Cv5zujpbZo7SZ50hqICxorzGB3w01Tds62R78b4wQctPA8rL%2ByshLkXQXs9BM8f9ULC5JywoL3i%2B98bHo%2F9JzYyqmCdUvC1ugiM%2F5%2BY63l49PvhdpoEkbn340BC6gShqus0164TuLh28VviKz6JwKssbPorWtoA%2Fx5RhSs%2FLarA%3D%3D'
year = 2024

data = pd.read_csv('basketballBrawl2024.csv')

final_week = 23

final_ranks = data[(data['Week'] == final_week)][['Team Name', 'Rank']]

regularData = data[data['Type'] == 'Regular']
# Filter for the most recent week
latest_week = regularData['Week'].max()
#recentRanks = regularData[regularData['Week'] == latest_week]['Rank']

recentData = regularData[regularData['Week'] == latest_week].copy()

# Create a new column for 'Record' as '[Cumulative Wins] - [Cumulative Losses]'
recentData['Record'] = recentData['Cumulative Wins'].astype(str) + " - " + recentData['Cumulative Losses'].astype(str)

# Select the columns you need for the table display
table_data = recentData[['Team Name', 'Record', 'Cumulative Points For', 'Cumulative Points Against']]

table_data = table_data.merge(final_ranks, on='Team Name')

table_data = table_data[['Rank', 'Team Name', 'Record', 'Cumulative Points For', 'Cumulative Points Against']]

print(table_data)



# data = data.merge(
#         players,
#         left_on=['Week', 'Team Name'],
#         right_on=['Week', 'Team Name'],
#         suffixes=('', '_player')
#     )
# team1 = 'Keegan It Real'
# team2 = 'New Jersey Eren'

# matchups = data[(data['Team Name'] == team1) & (data['Opponent Team Name'] == team2)]

# print(matchups)

# matchupsLineups = matchups.merge(players, on=['Year', 'Week', 'Team Name'])

# matchupsLineups = matchupsLineups['']

# print(matchupsLineups)


# for matchup in data:
#     print(matchup)
#     if matchup['Team Name'] == team1 and matchup['Opponent Team Name'] == team2:
#         year = matchup['Year']
#         week = matchup['Week']
#         print(str(year) + " " + str(week))
#         print(team1 + " Lineup")
#         print(players[players['Team Name'] == team1 and players['Year'] == year and players['Week'] == week])
#         print(team2 + " Lineup")
#         print(players[players['Team Name'] == team2 and players['Year'] == year and players['Week'] == week])