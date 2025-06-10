import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Load the data
data = pd.read_csv('basketballBrawl - Sheet2.csv')


# Group by Team Name and sum FPTS for each player
team_data = data.groupby(['Team Name', 'Player Name'])['FPTS'].sum().reset_index()

# Exclude players with negative FPTS
team_data = team_data[team_data['FPTS'] > 0]

# Calculate total FPTS per team
team_totals = team_data.groupby('Team Name')['FPTS'].sum().reset_index()
team_totals.rename(columns={'FPTS': 'Total FPTS'}, inplace=True)

# Merge total FPTS back to player data
team_data = team_data.merge(team_totals, on='Team Name')
team_data['Contribution'] = team_data['FPTS'] / team_data['Total FPTS']

# Plot pie chart for each team
# Plot pie chart for each team
for team in team_data['Team Name'].unique():
    team_players = team_data[team_data['Team Name'] == team]
    
    # Sort by FPTS and select the top 15 players
    top_players = team_players.nlargest(15, 'FPTS')
    
    # Calculate the sum of FPTS for other players
    other_players_contribution = team_players.loc[~team_players['Player Name'].isin(top_players['Player Name']), 'Contribution'].sum()
    
    # Create the 'Other' category
    other_data = pd.DataFrame({'Player Name': ['Other'], 'Contribution': [other_players_contribution]})
    
    # Combine top 15 players with 'Other'
    final_data = pd.concat([top_players[['Player Name', 'Contribution']], other_data])
    
    # Plot the pie chart
    plt.figure(figsize=(8, 8))
    plt.pie(
        final_data['Contribution'],
        labels=final_data['Player Name'],
        autopct='%1.1f%%',
        startangle=140
    )
    plt.title(f"{team} - Top 15 Player Contribution to Total FPTS (with 'Other')")
    plt.show()





# # Group by Team Name and sum FPTS for each position
# team_data = data.groupby(['Team Name', 'Position'])['FPTS'].sum().reset_index()

# # Exclude players with negative FPTS
# team_data = team_data[team_data['FPTS'] > 0]

# # Calculate total FPTS per team
# team_totals = team_data.groupby('Team Name')['FPTS'].sum().reset_index()
# team_totals.rename(columns={'FPTS': 'Total FPTS'}, inplace=True)

# # Merge total FPTS back to positional data
# team_data = team_data.merge(team_totals, on='Team Name')
# team_data['Contribution'] = team_data['FPTS'] / team_data['Total FPTS']

# # Plot pie chart for each team
# for team in team_data['Team Name'].unique():
#     team_players = team_data[team_data['Team Name'] == team]
#     plt.figure(figsize=(8, 8))
#     plt.pie(
#         team_players['Contribution'],
#         labels=team_players['Position'],
#         autopct='%1.1f%%',
#         startangle=140
#     )
#     plt.title(f"{team} - Position Contribution to Total FPTS")
#     plt.show()