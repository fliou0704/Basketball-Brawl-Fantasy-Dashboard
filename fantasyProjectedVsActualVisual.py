from espn_api.basketball import League
import pandas as pd
from datetime import datetime
import time
import matplotlib.pyplot as plt
import seaborn as sns

### - Projected points at start of season vs. end of season results
### - Print top players who outperformed their projections
### - Print bottom players who underperformed their projections

df = pd.read_csv('projectedVsActual.csv')

df["Projected"] = pd.to_numeric(df["Projected"])
df["Actual"] = pd.to_numeric(df["Actual"])
df = df.groupby('Team').apply(lambda x: x.nlargest(12, 'Projected')).reset_index(drop=True) # Select only top 12 performing players for each team


#Create a bar plot for each team
teams = df['Team'].unique()

y_min = df['Difference'].min() - 100
y_max = df['Difference'].max() + 100

for team in teams:
    team_df = df[df['Team'] == team].sort_values(by='Difference', ascending=False)
    
    plt.figure(figsize=(10, 6))
    sns.barplot(
        x='Player', y='Difference', data=team_df,
        palette='coolwarm'
    )
    plt.title(f'{team} - Top Players Difference Between Projected and Actual Score')
    plt.xlabel('Player')
    plt.ylabel('Difference')
    plt.xticks(rotation=45, ha='right')

    # Set consistent y-axis limits
    plt.ylim(y_min, y_max)

    plt.tight_layout()
    plt.show()


# top_20_outperformers = df.nlargest(20, 'Difference')
# #print(top_20_outperformers)

# # Create the bar plot
# plt.figure(figsize=(12, 8))
# sns.barplot(
#     x='Difference', y='Player', data=top_20_outperformers,
#     hue='Team', dodge=False, palette='muted'
# )

# # Set plot title and labels
# plt.title('Top 20 Players by Difference')
# plt.xlabel('Difference')
# plt.ylabel('Player')
# plt.legend(title='Team', bbox_to_anchor=(1.05, 1), loc='upper left')
# plt.tight_layout()

# # Show plot
# plt.show()




# bottom_20_underperformers = df.nsmallest(20, 'Difference')
# #print(top_20_outperformers)

# # Create the bar plot
# plt.figure(figsize=(12, 8))
# sns.barplot(
#     x='Difference', y='Player', data=bottom_20_underperformers,
#     hue='Team', dodge=False, palette='muted'
# )

# # Set plot title and labels
# plt.title('Top 20 Players by Difference')
# plt.xlabel('Difference')
# plt.ylabel('Player')
# plt.legend(title='Team', bbox_to_anchor=(1.05, 1), loc='upper left')
# plt.tight_layout()

# # Show plot
# plt.show()

