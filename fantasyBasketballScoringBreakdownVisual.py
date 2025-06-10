import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Load the data
data = pd.read_csv('basketballBrawl - Sheet2.csv')


# We're combining related stats to create positive, representative values
#Original
data['Free Throws'] = data['FTA'] + (data['FTM'] * 2)
data['3PT Shooting'] = (data['3PM'] * 4) # +3 for three points -1 for FGA +2 for FGM (+4 total)
data['Scoring'] = data['FGA'] + data['FGM'] + (data['PTS'] - data['FTM'] - (data['3PM'] * 3))  # Using FTM, FTA, FGA, FGM, PTS as a proxy for all-around scoring performance

#Simplified
#data['Scoring'] = data['FTA'] + data['FTM'] + data['FGA'] + data['FGM'] + data['PTS'] + data['3PM'] # Using FTM, FTA, FGA, FGM, PTS, 3PM as a proxy for all-around scoring performance

data['Playmaking'] = data['TO'] + data['AST']  # Using AST, TO as a proxy for playmaking performance

#Optional
#data['Defense'] = (data['BLK'] + data['STL'] + data['REB'])  # Using BLK, STL, REB as a proxy for defensive performance

# List of statistics to use for the pie chart
#Original, do not use with optional above
stat_columns = ['REB', 'BLK', 'STL', 'Free Throws', '3PT Shooting', 'Scoring', 'Playmaking']
#Simplified
#stat_columns = ['Scoring', 'Playmaking', 'Defense']

# Aggregate the data by Team Name to get total values for each stat
team_stats = data.groupby(['Team Name'])[stat_columns].sum().reset_index()

# Calculate the number of teams and set up the grid dimensions
num_teams = len(team_stats)
cols = 3  # Define the number of columns for the grid
rows = 4  # Calculate the number of rows needed

# Create a figure with subplots
fig, axes = plt.subplots(rows, cols, figsize=(15, 5 * rows))
fig.suptitle('Statistics Breakdown by Team (Total Data)', fontsize=16)

# Flatten the axes array for easier indexing
axes = axes.flatten()

for i, (idx, team_data) in enumerate(team_stats.iterrows()):
    # Get the pie data for the current team
    values = team_data[stat_columns].values
    labels = stat_columns
    team_name = team_data['Team Name']

    # Plot the pie chart in the ith subplot
    axes[i].pie(values, labels=labels, autopct='%1.1f%%', startangle=140)
    axes[i].set_title(f'{team_name}')

# Hide any unused subplots
for j in range(i + 1, len(axes)):
    axes[j].axis('off')

plt.tight_layout(rect=[0, 0, 1, 0.96])  # Adjust layout to fit title
plt.show()