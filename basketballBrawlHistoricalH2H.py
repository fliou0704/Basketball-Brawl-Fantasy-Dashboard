from dash import html, dcc, Input, Output
import pandas as pd

def get_h2h_layout(data):
    # Get latest team names for each team ID
    latest_year = data["Year"].max()
    latest_year_data = data[data["Year"] == latest_year]
    latest_week = latest_year_data["Week"].max()
    latest_week_data = latest_year_data[latest_year_data["Week"] == latest_week]
    latest_teams = latest_week_data[["Team ID", "Team Name"]]
    team_options = [
        {"label": row["Team Name"], "value": row["Team ID"]} for _, row in latest_teams.iterrows()
    ]

    return html.Div([
        html.H2("Historical Head-to-Head Matchups"),

        html.Div([
            html.Label("Team 1:"),
            dcc.Dropdown(
                id="h2h-team1-dropdown",
                options=team_options,
                placeholder="Select Team 1",
                value=None,
                clearable=True
            ),
        ], style={'width': '45%', 'display': 'inline-block', 'marginRight': '5%'}),

        html.Div([
            html.Label("Team 2:"),
            dcc.Dropdown(
                id="h2h-team2-dropdown",
                options=team_options,
                placeholder="Select Team 2",
                value=None,
                clearable=True
            ),
        ], style={'width': '45%', 'display': 'inline-block'}),

        html.Div(id="h2h-result")
    ])

def register_h2h_callbacks(app, data):
    @app.callback(
        Output("h2h-result", "children"),
        Input("h2h-team1-dropdown", "value"),
        Input("h2h-team2-dropdown", "value")
    )
    def update_h2h(team1_id, team2_id):
        if team1_id is None or team2_id is None:
            return html.P("Select two teams!")

        # Get team names for display
        latest_year = data["Year"].max()
        latest_year_data = data[data["Year"] == latest_year]
        latest_week = latest_year_data["Week"].max()
        latest_week_data = latest_year_data[latest_year_data["Week"] == latest_week]
        team1_name = latest_week_data[latest_week_data["Team ID"] == team1_id]["Team Name"].iloc[0]
        team2_name = latest_week_data[latest_week_data["Team ID"] == team2_id]["Team Name"].iloc[0]

        # Filter for matchups between the two teams
        h2h_data = data[((data["Team ID"] == team1_id) & (data["Opponent Team ID"] == team2_id))]

        if h2h_data.empty:
            return html.P("These teams have never played before.")

        # Calculate totals
        total_games = len(h2h_data)
        total_wins = h2h_data["Win"].sum()
        total_losses = total_games - total_wins

        # Breakdown by game type
        regular = h2h_data[h2h_data["Type"] == "Regular"]
        playoffs = h2h_data[h2h_data["Type"] == "Playoffs"]

        regular_wins = regular["Win"].sum()
        regular_losses = len(regular) - regular_wins

        playoff_wins = playoffs["Win"].sum()
        playoff_losses = len(playoffs) - playoff_wins

        return html.Div([
            html.H3(f"{team1_name} vs. {team2_name}"),
            html.P(f"Overall Record: {int(total_wins)} - {int(total_losses)}"),
            html.P(f"Regular Season: {int(regular_wins)} - {int(regular_losses)}"),
            html.P(f"Playoffs: {int(playoff_wins)} - {int(playoff_losses)}")
        ])
    # Callback to update dropdown options
    @app.callback(
        Output("h2h-team1-dropdown", "options"),
        Output("h2h-team2-dropdown", "options"),
        Input("h2h-team1-dropdown", "value"),
        Input("h2h-team2-dropdown", "value")
    )
    def update_dropdown_options(selected_team1, selected_team2):
        latest_teams = data.sort_values("Year").drop_duplicates("Team ID", keep="last")
        all_teams = latest_teams[["Team ID", "Team Name"]]

        # Filter options based on selection
        options1 = [
            {"label": name, "value": teamid}
            for teamid, name in zip(all_teams["Team ID"], all_teams["Team Name"])
            if teamid != selected_team2
        ]
        options2 = [
            {"label": name, "value": teamid}
            for teamid, name in zip(all_teams["Team ID"], all_teams["Team Name"])
            if teamid != selected_team1
        ]
        return options1, options2