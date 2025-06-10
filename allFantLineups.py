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
### - Add weekly matchups tab so people can look at each week and see the scores, ranked teams by points scored that week, "ideal" lineup for that week
### - Add an awards tab for end of season awards (all nba lineup, mvp, best free agent pickup, league slut, ...)
### - Add some way for players to see every 100 point performance




### espn_s2 for 2021-2023
# espn_s2 = 'AEB%2BZ33nD3CVjTy1%2BY7Y6lYP5KSTfdAI6lUjIpSJ8WHLUyjlIMjYKiJlolvuDTyLPBjdhVHIE5UlyyOh6M%2BWtfB1WA5v2CtQhc1CVjmoF%2B%2BgYmTNE%2FDJgSUC0ws0N9S%2Bermktd4xrMRGnr6C%2FpE2hqqe%2BSjMMAVw941%2F%2BAqJw5qqPpT4LfO4BQuSGepw20APuVapbRM3uzCzqadS91HCK0%2BTQhEpm1lpVCGlqCx%2F6rb0UwYNqjJeLkbuXXbrkqK9mPrg5QAqGRI914K2U%2Bah2yD08dXZ8xfYB7K0ilPeqJPKJA%3D%3D'

league_id = 609694684
swid = "{462737C8-F92F-4033-8AD6-1D877AC43C1D}"
espn_s2 = 'AEAgnCeltBfv4nKLUgjlax5tsKzVho%2B6cA1L370VKGvF%2B8hlSX4dpV6Gv7kWYNR5t3zCcNNNwmdXlDPD3HMHLCK%2B6EjbZSYRcIKDl32HUTlKJYweuLKQkzjVDaj89PrtCQ6Cv5zujpbZo7SZ50hqICxorzGB3w01Tds62R78b4wQctPA8rL%2ByshLkXQXs9BM8f9ULC5JywoL3i%2B98bHo%2F9JzYyqmCdUvC1ugiM%2F5%2BY63l49PvhdpoEkbn340BC6gShqus0164TuLh28VviKz6JwKssbPorWtoA%2Fx5RhSs%2FLarA%3D%3D'
year = 2024

data = pd.read_csv('basketballBrawl2024.csv')

players = pd.read_csv('basketballBrawl - Sheet2.csv')

print(players)

df = players

# Melt the positions columns into one column
positions_df = pd.melt(df, id_vars=['Player Name', 'Team Name', 'FPTS'], value_vars=['Position', 'Position2', 'Position3'],
                       var_name='Position_Type', value_name='Position_Final')

# Drop rows where 'Position' is NaN
positions_df = positions_df.dropna(subset=['Position_Final'])

# Group by 'Player Name', 'Team Name', and 'Position', summing the 'FPTS'
player_points = positions_df.groupby(['Player Name', 'Team Name', 'Position_Final'])['FPTS'].sum().reset_index()

# Sort by FPTS in descending order so the highest scoring players come first
player_points = player_points.sort_values(by='FPTS', ascending=False)

# Define positions and create an empty list to store the final lineup
positions = ['PG', 'SG', 'SF', 'PF', 'C']
all_nba_lineup1 = []

# Track players already selected to avoid duplicates
selected_players = set()

# Iterate over each position
for position in positions:
    # Filter to only players eligible for the current position and not already selected
    position_players = player_points[(player_points['Position_Final'] == position) & (~player_points['Player Name'].isin(selected_players))]
    
    # Check if there are any eligible players left for this position
    if not position_players.empty:
        # Get the top player for this position
        best_player = position_players.iloc[0]
        
        # Append the best player’s details to the lineup
        all_nba_lineup1.append(best_player)
        
        # Mark this player as selected
        selected_players.add(best_player['Player Name'])

# Convert the lineup to a DataFrame for better presentation
lineup_df = pd.DataFrame(all_nba_lineup1).reset_index(drop=True)

# Display the 'All NBA' lineup
print(lineup_df)


all_nba_lineup2 = []

# Iterate over each position
for position in positions:
    # Filter to only players eligible for the current position and not already selected
    position_players = player_points[(player_points['Position_Final'] == position) & (~player_points['Player Name'].isin(selected_players))]
    
    # Check if there are any eligible players left for this position
    if not position_players.empty:
        # Get the top player for this position
        best_player = position_players.iloc[0]
        
        # Append the best player’s details to the lineup
        all_nba_lineup2.append(best_player)
        
        # Mark this player as selected
        selected_players.add(best_player['Player Name'])

# Convert the lineup to a DataFrame for better presentation
lineup_df = pd.DataFrame(all_nba_lineup2).reset_index(drop=True)

# Display the 'All NBA' lineup
print(lineup_df)

all_nba_lineup3 = []

# Iterate over each position
for position in positions:
    # Filter to only players eligible for the current position and not already selected
    position_players = player_points[(player_points['Position_Final'] == position) & (~player_points['Player Name'].isin(selected_players))]
    
    # Check if there are any eligible players left for this position
    if not position_players.empty:
        # Get the top player for this position
        best_player = position_players.iloc[0]
        
        # Append the best player’s details to the lineup
        all_nba_lineup3.append(best_player)
        
        # Mark this player as selected
        selected_players.add(best_player['Player Name'])

# Convert the lineup to a DataFrame for better presentation
lineup_df = pd.DataFrame(all_nba_lineup3).reset_index(drop=True)

# Display the 'All NBA' lineup
print(lineup_df)