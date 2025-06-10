import dash
from dash import dcc, html, Input, Output, State, callback_context, Dash
import pandas as pd
import plotly.express as px
import dash_bootstrap_components as dbc
import plotly.graph_objects as go


data = pd.read_csv('basketballBrawlHistoricalData.csv')

data = data[data['Year'] > 2022]

players = pd.read_csv('basketballBrawl - Sheet2.csv')

player_data = data.merge(
        players,
        left_on=['Week', 'Team Name'],
        right_on=['Week', 'Team Name'],
        suffixes=('', '_player')
    )

df = data

# Get latest team names by Team ID
latest_team_names = df.sort_values(by="Year").drop_duplicates(subset="Team ID", keep="last")[["Team ID", "Team Name"]]

def display_matchup_with_lineups(team1_id, team2_id, week):
    # Filter the head-to-head data for the specific matchup
    matchup = df[(df['Team ID'] == team1_id) & (df['Opponent Team ID'] == team2_id) & (df['Week'] == week)]
    team1_name = df[df['Team ID'] == team1_id]['Team Name']
    team2_name = df[df['Team ID'] == team2_id]['Team Name']
    

    # Separate lineups for team1 and team2
    team1_lineup = player_data[player_data['Team ID'] == team1_id][['Player Name', 'Player Position', 'Player Points']]
    team2_lineup = player_data[player_data['Team ID'] == team2_id][['Player Name', 'Player Position', 'Player Points']]

    # Create Plotly layout for the matchup lineups
    fig = go.Figure()

    # Add team1 lineup
    fig.add_trace(go.Table(
        header=dict(values=[f"{team1_name} Lineup", "Position", "Points"]),
        cells=dict(values=[team1_lineup['Player Name'], team1_lineup['Player Position'], team1_lineup['Player Points']])
    ))

    # Add team2 lineup
    fig.add_trace(go.Table(
        header=dict(values=[f"{team2_name} Lineup", "Position", "Points"]),
        cells=dict(values=[team2_lineup['Player Name'], team2_lineup['Player Position'], team2_lineup['Player Points']])
    ))

    fig.update_layout(title_text=f"Matchup: {team1_name} vs {team2_name} - Week {week}")
    fig.show()

# Create a function to calculate the head-to-head record
def calculate_head_to_head(team1_id, team2_id):
    # Filter data to show only matches between team1 and team2
    filtered = df[((df['Team ID'] == team1_id) & (df['Opponent Team ID'] == team2_id)) |
                  ((df['Team ID'] == team2_id) & (df['Opponent Team ID'] == team1_id))]
    
    # Calculate total, regular season, and playoffs records specifically from team1's perspective
    total_wins = filtered[(filtered['Team ID'] == team1_id) & (filtered['Win'] == 1)].shape[0]
    total_losses = filtered[(filtered['Team ID'] == team1_id) & (filtered['Loss'] == 1)].shape[0]
    total_record = (total_wins, total_losses)

    reg_season_wins = filtered[(filtered['Team ID'] == team1_id) & 
                               (filtered['Win'] == 1) & (filtered['Type'] == 'Regular')].shape[0]
    reg_season_losses = filtered[(filtered['Team ID'] == team1_id) & 
                                 (filtered['Loss'] == 1) & (filtered['Type'] == 'Regular')].shape[0]
    reg_season_record = (reg_season_wins, reg_season_losses)

    playoff_wins = filtered[(filtered['Team ID'] == team1_id) & 
                            (filtered['Win'] == 1) & (filtered['Type'] == 'Playoffs')].shape[0]
    playoff_losses = filtered[(filtered['Team ID'] == team1_id) & 
                              (filtered['Loss'] == 1) & (filtered['Type'] == 'Playoffs')].shape[0]
    playoff_record = (playoff_wins, playoff_losses)

    return total_record, reg_season_record, playoff_record

# Initialize the Dash app
app = Dash(__name__)

app.layout = html.Div([
    html.H1("Fantasy Basketball Head-to-Head Record"),
    
    # Dropdowns for selecting Team 1 and Team 2
    html.Label("Select Team 1:"),
    dcc.Dropdown(
        id="team1_dropdown",
        options=[{"label": name, "value": team_id} for team_id, name in latest_team_names.values],
        placeholder="Select Team 1"
    ),
    
    html.Label("Select Team 2:"),
    dcc.Dropdown(
        id="team2_dropdown",
        options=[{"label": name, "value": team_id} for team_id, name in latest_team_names.values],
        placeholder="Select Team 2"
    ),
    
    # Display head-to-head record
    html.Div(id="output_record")
])

# Callback to update the head-to-head record
@app.callback(
    Output("output_record", "children"),
    [Input("team1_dropdown", "value"),
     Input("team2_dropdown", "value")]
)
def update_record(team1_id, team2_id):
    if not team1_id or not team2_id:
        return "Please select both teams."
    
    total, reg_season, playoffs = calculate_head_to_head(team1_id, team2_id)
    return html.Div([
        html.H3("Head-to-Head Record"),
        html.P(f"Total Record: {total[0]} - {total[1]}"),
        html.P(f"Regular Season Record: {reg_season[0]} - {reg_season[1]}"),
        html.P(f"Playoffs Record: {playoffs[0]} - {playoffs[1]}")
    ])

# Run the app
if __name__ == "__main__":
    app.run_server(debug=True)