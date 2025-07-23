from dash import html, dcc, Input, Output
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dataStore import playerMatchup, data, activityData

### TODO:
### - Reflect team stat rankings to be only regular season
### - Fix all-time roster to skip showing when a player was kept, maybe higlight the "active" players
### - Add yearly roster, similar to all-time roster with acquisition status and percentage mentioned below
### - Instead of pie chart for points by player, just show percentage contribution on yearly roster
### - Add projected points vs. actual graphic (maybe)
### - Add trade history for each team

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

# Get most recent year for each team
latest_team_names = (
    league_data.sort_values("Year", ascending=False)
    .drop_duplicates("Team ID")[["Team ID", "Team Name"]]
)

team_dropdown_options = [
    {"label": row["Team Name"], "value": row["Team ID"]}
    for _, row in latest_team_names.iterrows()
]

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
                style={"width": "50%", "margin-bottom": "20px"},
                searchable=False
            )
        ]),
        html.Div([
            dcc.Dropdown(
                id="year-dropdown",
                options=year_dropdown_options,
                value="Summary",
                style={"width": "50%"},
                searchable=False,
                clearable=False
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
    def update_team_stats(team_id, selected_year):
        if not team_id:
            return html.Div("Please select a team")
        
        # Get most recent team name for display
        team_name_row = league_data[league_data["Team ID"] == team_id].sort_values("Year", ascending=False).head(1)
        team_name = team_name_row["Team Name"].values[0] if not team_name_row.empty else f"Team {team_id}"

        if selected_year == "Summary" or selected_year is None:
            # Filter team data
            team_data = players[players["Team ID"] == team_id]

            # Group by Player ID instead of name to avoid name mismatches
            roster_df = team_data.groupby("Player ID")["FPTS"].sum().reset_index()
            roster_df = roster_df.sort_values("FPTS", ascending=False)

            # Bring in player names (latest one available)
            latest_names = (
                team_data.sort_values("Year", ascending=False)
                .drop_duplicates(subset="Player ID")[["Player ID", "Player Name"]]
            )
            roster_df = roster_df.merge(latest_names, on="Player ID", how="left")

            # Filter activity data
            activity = activityData.copy()
            activity = activity[activity["Team ID"] == team_id]
            activity["Datetime"] = pd.to_datetime(activity["Date"] + " " + activity["Time"])
            activity = activity.sort_values("Datetime", ascending=False)

            # Function to find original (non-KEEPER) acquisition action
            def find_original_action(player_id, df):
                player_history = df[df["Player ID"] == player_id]
                for _, row in player_history.iterrows():
                    if row["Action"] != "KEEPER":
                        return row["Action"], row["Date"]
                return "KEEPER", None

            # Build acquisition history based on Player ID
            original_actions = []
            for player_id in roster_df["Player ID"].unique():
                player_history = activity[activity["Player ID"] == player_id]
                if not player_history.empty:
                    action, date = find_original_action(player_id, player_history)
                else:
                    action, date = "—", "—"
                original_actions.append({"Player ID": player_id, "Action": action, "Date": date})

            recent_activity = pd.DataFrame(original_actions)

            # Merge with roster
            roster = roster_df.merge(recent_activity, on="Player ID", how="left")
            roster = roster.sort_values("FPTS", ascending=False)

            # Build HTML table rows
            table_rows = []
            for _, row in roster.iterrows():
                table_rows.append(html.Tr([
                    html.Td(row["Player Name"]),
                    html.Td(f"{row['FPTS']:.2f}"),
                    html.Td(row["Action"] if pd.notna(row["Action"]) else "—"),
                    html.Td(row["Date"] if pd.notna(row["Date"]) else "—")
                ]))

            roster_table = html.Table([
                html.Thead(html.Tr([
                    html.Th("Player Name"),
                    html.Th("Total FPTS"),
                    html.Th("Last Action"),
                    html.Th("Last Action Date")
                ])),
                html.Tbody(table_rows)
            ])

            # All-Time Records (excluding Consolation)
            records = league_data[(league_data["Team ID"] == team_id) & (league_data["Type"] != "Consolation")]
            total_wins = records["Win"].sum()
            total_losses = records["Loss"].sum()

            regular = records[records["Type"] == "Regular"]
            playoff = records[records["Type"] == "Playoffs"]

            reg_wins = regular["Win"].sum()
            reg_losses = regular["Loss"].sum()
            po_wins = playoff["Win"].sum()
            po_losses = playoff["Loss"].sum()

            return html.Div([
                html.H3(f"Summary for {team_name}"),
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
        year_data = players[(players["Year"] == int(selected_year)) & (players["Team ID"] == team_id)]

        # If no data, return message
        if year_data.empty:
            return html.Div(f"No data for {team_name} in {selected_year}")

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

        # Style dictionary for table cells
        cell_style = {
            "textAlign": "center",
            "padding": "10px"  # Adjust as needed for spacing
        }

        ranking_labels = []
        ranking_images = []
        ranking_values = []

        rank_to_image = {
            1: "first.png",
            2: "second.png",
            3: "third.png",
            4: "fourth.png",
            5: "fifth.png",
            6: "sixth.png",
            7: "seventh.png",
            8: "eighth.png",
            9: "ninth.png",
            10: "tenth.png"
        }

        year_df = players[players["Year"] == int(selected_year)]

        for stat_label, func in stat_cols.items():
            team_stat = func(year_data)
            all_stats = year_df.groupby("Team Name").apply(func).dropna()

            if team_name not in all_stats:
                rank = "N/A"
            else:
                rank = int(all_stats.rank(ascending=False, method="min").loc[team_name])

            # Row 1: Stat labels
            ranking_labels.append(html.Td(stat_label, style=cell_style))

            # Row 2: Rank images or N/A
            if isinstance(rank, int):
                rank_img = rank_to_image.get(rank)
                if rank_img:
                    rank_display = html.Img(
                        src=f"/assets/placements/{rank_img}",
                        height="30px",
                        style={"display": "block", "margin": "0 auto"}  # Center image
                    )
                else:
                    rank_display = str(rank)
            else:
                rank_display = "N/A"

            ranking_images.append(html.Td(rank_display, style=cell_style))

            # Row 3: Stat values
            value_display = f"{team_stat:.2f}" if pd.notna(team_stat) else "N/A"
            ranking_values.append(html.Td(value_display, style=cell_style))

        return html.Div([
            html.H3(f"{team_name} - {selected_year} Stat Rankings"),
            html.Table([
                html.Tbody([
                    html.Tr(ranking_labels),
                    html.Tr(ranking_images),
                    html.Tr(ranking_values),
                ])
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