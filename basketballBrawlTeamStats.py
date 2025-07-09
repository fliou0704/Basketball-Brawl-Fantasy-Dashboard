from dash import html, dcc, Input, Output
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dataStore import playerMatchup, data

### TODO:
### - Mariokart style stat rankings
### - Reflect team rankings to be only regular season
### - All-time team roster along with how each player was acquired/dropped
### - All-time record and winning percentage with playoff splits

# Sample team data - Replace with your actual data
players = playerMatchup
league_data = data

players["FGM"] = players["FGM"] / 2
players["FGA"] = players["FGA"] * -1
players["FTA"] = players["FTA"] * -1
players["AST"] = players["AST"] / 2
players["STL"] = players["STL"] / 4
players["BLK"] = players["BLK"] / 4
players["TO"] = players["TO"] / -2

years = sorted(players['Year'].unique())
years.sort(reverse=True)

unique_teams = players[players["Year"] == max(years)]["Team Name"].unique()

# Dropdown options (list of dictionaries with 'label' and 'value')
team_dropdown_options = [{"label": team, "value": team} for team in unique_teams]

year_dropdown_options = [{"label": "Summary", "value": "Summary"}] + [
    {"label": str(yr), "value": yr} for yr in years
]

# Function to generate the layout for the team stats page
def get_team_layout():
    return html.Div([
        html.Div([
            dcc.Dropdown(
                id="team-dropdown",
                options=team_dropdown_options,
                placeholder="Select a team",
                style={"width": "50%", "margin-bottom": "20px"}
            )
        ]),
        html.Div([
            dcc.Dropdown(
                id="year-dropdown",
                options=year_dropdown_options,
                value="Summary",
                style={"width": "50%"}
            )
        ], id="year-dropdown-container", style={"display": "none"}),
        html.Div(id="team-stats-display")
    ])

def register_team_callbacks(app):
    @app.callback(
        Output("year-dropdown-container", "style"),
        Input("team-dropdown", "value")
    )
    def toggle_year_dropdown(team):
        return {"display": "block"} if team else {"display": "none"}

    @app.callback(
        Output("team-stats-display", "children"),
        [Input("team-dropdown", "value"), Input("year-dropdown", "value")]
    )
    def update_team_stats(team, selected_year):
        if not team:
            return html.Div("Please select a team")

        if selected_year == "Summary" or selected_year is None:
            # All-Time Roster
            team_data = players[players["Team Name"] == team]
            roster_df = team_data.groupby("Player Name")["FPTS"].sum().reset_index()
            roster_df = roster_df.sort_values("FPTS", ascending=False)

            roster_table = html.Table([
                html.Thead(html.Tr([html.Th("Player Name"), html.Th("Total FPTS")]))
            ] + [
                html.Tr([html.Td(row["Player Name"]), html.Td(f"{row['FPTS']:.2f}")]) for _, row in roster_df.iterrows()
            ])

            # All-Time Records (excluding Consolation)
            records = league_data[(league_data["Team Name"] == team) & (league_data["Type"] != "Consolation")]
            total_wins = records["Win"].sum()
            total_losses = records["Loss"].sum()

            regular = records[records["Type"] == "Regular"]
            playoff = records[records["Type"] == "Playoffs"]

            reg_wins = regular["Win"].sum()
            reg_losses = regular["Loss"].sum()
            po_wins = playoff["Win"].sum()
            po_losses = playoff["Loss"].sum()

            return html.Div([
                html.H3(f"Summary for {team}"),
                html.Br(),
                html.H4("All-Time Record"),
                html.P(f"Overall Record: {total_wins} - {total_losses}"),
                html.P(f"Regular Season: {reg_wins} - {reg_losses}"),
                html.P(f"Playoffs: {po_wins} - {po_losses}"),
                html.Br(),
                html.H4("All-Time Roster"),
                roster_table
            ])
        
        # Filter for selected year and team
        year_data = players[(players["Year"] == int(selected_year)) & (players["Team Name"] == team)]

        # If no data, return message
        if year_data.empty:
            return html.Div(f"No data for {team} in {selected_year}")

        # === Stat Rankings ===
        stat_cols = {
            "FG%": lambda df: df["FGM"].sum() / df["FGA"].replace(0, pd.NA).sum() * 100,
            "FT%": lambda df: df["FTM"].sum() / df["FTA"].replace(0, pd.NA).sum() * 100,
            "3PM": lambda df: df["3PM"].sum(),
            "REB": lambda df: df["REB"].sum(),
            "AST/TO": lambda df: df["AST"].sum() / df["TO"].replace(0, pd.NA).sum(),
            "STL": lambda df: df["STL"].sum(),
            "BLK": lambda df: df["BLK"].sum(),
            "PTS": lambda df: df["PTS"].sum(),
            "FPTS": lambda df: df["FPTS"].sum()
        }

        ranking_table = []
        year_df = players[players["Year"] == int(selected_year)]

        for stat_label, func in stat_cols.items():
            # Compute team value
            team_stat = func(year_data)

            # Compute all team values
            all_stats = year_df.groupby("Team Name").apply(func)

            # Drop NaNs and rank
            all_stats = all_stats.dropna()
            if team not in all_stats:
                rank = "N/A"
            else:
                rank = int(all_stats.rank(ascending=False, method="min").loc[team])

            ranking_table.append(html.Tr([
                html.Td(stat_label),
                html.Td(rank),
                html.Td(f"{team_stat:.2f}" if pd.notna(team_stat) else "N/A")
            ]))

        return html.Div([
            html.H3(f"{team} - {selected_year} Stat Rankings"),
            html.Table([
                html.Thead(html.Tr([html.Th("Stat"), html.Th("Rank"), html.Th("Value")])),
                html.Tbody(ranking_table)
            ])
        ])






# df = pd.read_csv('projectedVsActual.csv')
# df["Projected"] = pd.to_numeric(df["Projected"])
# df["Actual"] = pd.to_numeric(df["Actual"])
# #df = df.groupby('Team').apply(lambda x: x.nlargest(12, 'Projected')).reset_index(drop=True)

# # Calculate y-axis limits for consistency
# y_min = df['Difference'].min() - 100
# y_max = df['Difference'].max() + 100

# def create_team_difference_chart(team):
#     # Filter data for the selected team
#     team_df = df[df['Team'] == team].sort_values(by='Difference', ascending=False)

#     # Create a Plotly bar chart
#     fig = px.bar(
#         team_df,
#         x='Player',
#         y='Difference',
#         title=f'{team} - Top Players Difference Between Projected and Actual Points Scored',
#         labels={'Difference': 'Difference', 'Player': 'Player'},
#         color='Difference',  # Using color to show differences
#         color_continuous_scale='bluered'
#     )

#     # Set consistent y-axis limits
#     fig.update_yaxes(range=[y_min, y_max])

#     # Update layout for readability
#     fig.update_layout(
#         xaxis_tickangle=45,
#         xaxis_title='Player',
#         yaxis_title='Difference',
#         margin=dict(l=20, r=20, t=50, b=50)
#     )

#     return fig





# # Combine related stats
# pieData = players
# pieData['Free Throws'] = pieData['FTA'] + (pieData['FTM'] * 2)
# pieData['3PT Shooting'] = (pieData['3PM'] * 4)  # +3 for three points -1 for FGA +2 for FGM (+4 total)
# pieData['2PT Scoring'] = pieData['FGA'] + pieData['FGM'] + (pieData['PTS'] - pieData['FTM'] - (pieData['3PM'] * 3))  # Using FTM, FTA, FGA, FGM, PTS as a proxy for all-around scoring performance
# pieData['Playmaking'] = pieData['TO'] + pieData['AST']  # Using AST, TO as a proxy for playmaking performance

# # List of statistics to use for the pie chart
# stat_columns = ['REB', 'BLK', 'STL', 'Free Throws', '3PT Shooting', '2PT Scoring', 'Playmaking']

# # Aggregate the data by Team Name to get total values for each stat
# team_stats = pieData.groupby(['Team Name'])[stat_columns].sum().reset_index()

# # Create a function to generate the pie chart for a selected team
# def create_team_pie_chart(team):
#     # Get the data for the selected team
#     team_data = team_stats[team_stats['Team Name'] == team].iloc[0]
    
#     # Get the values for the pie chart
#     values = team_data[stat_columns].values
#     labels = stat_columns

#     # Create the pie chart
#     fig = go.Figure(data=[go.Pie(
#         labels=labels,
#         values=values,
#         textinfo='percent',
#         title=f'{team} - Statistics Breakdown'
#     )])

#     # Update layout
#     fig.update_layout(
#         showlegend=True,
#         height=500,
#         title_text=f'{team} - Statistics Breakdown'
#     )

#     return fig






# # Group by Team Name and sum FPTS for each position
# position_data = players.groupby(['Team Name', 'Position'])['FPTS'].sum().reset_index()

# # Exclude players with negative FPTS
# position_data = position_data[position_data['FPTS'] > 0]

# # Calculate total FPTS per team
# position_totals = position_data.groupby('Team Name')['FPTS'].sum().reset_index()
# position_totals.rename(columns={'FPTS': 'Total FPTS'}, inplace=True)

# # Merge total FPTS back to positional data
# position_data = position_data.merge(position_totals, on='Team Name')
# position_data['Contribution'] = position_data['FPTS'] / position_data['Total FPTS']

# def create_positional_pie_chart(team):
#     # Get the data for the selected team
#     team_players = position_data[position_data['Team Name'] == team]
    
#     fig = go.Figure(data=[go.Pie(
#         labels=team_players['Position'],
#         values=team_players['Contribution'],
#         hoverinfo='label+percent',
#         textinfo='label+percent'
#     )])
#     fig.update_layout(title=f"{team} - Position Contribution to Total FPTS", showlegend=True)
#     return fig







# # Group by Team Name and sum FPTS for each player
# player_data = players.groupby(['Team Name', 'Player Name'])['FPTS'].sum().reset_index()

# # Exclude players with negative FPTS
# player_data = player_data[player_data['FPTS'] > 0]

# # Calculate total FPTS per team
# player_totals = player_data.groupby('Team Name')['FPTS'].sum().reset_index()
# player_totals.rename(columns={'FPTS': 'Total FPTS'}, inplace=True)

# # Merge total FPTS back to player data
# player_data = player_data.merge(player_totals, on='Team Name')
# player_data['Contribution'] = player_data['FPTS'] / player_data['Total FPTS']

# # Function to plot pie chart for selected team
# def plot_player_pie_chart(team):
#     # Filter the data for the selected team
#     team_players = player_data[player_data['Team Name'] == team]
    
#     # Sort by FPTS and select the top 15 players
#     top_players = team_players.nlargest(15, 'FPTS')
    
#     # Calculate the sum of FPTS for other players
#     other_players_contribution = team_players.loc[~team_players['Player Name'].isin(top_players['Player Name']), 'Contribution'].sum()
    
#     # Create the 'Other' category
#     other_data = pd.DataFrame({'Player Name': ['Other'], 'Contribution': [other_players_contribution]})
    
#     # Combine top 15 players with 'Other'
#     final_data = pd.concat([top_players[['Player Name', 'Contribution']], other_data])

#     # Plot the pie chart using Plotly
#     fig = go.Figure(data=[go.Pie(
#         labels=final_data['Player Name'],
#         values=final_data['Contribution'],
#         textinfo='label+percent',
#     )])
    
#     fig.update_layout(
#         title=f"{team} - Top 15 Player Contribution to Total FPTS (with 'Other')",
#         showlegend=True
#     )

#     return fig