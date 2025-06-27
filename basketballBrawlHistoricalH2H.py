from dash import html, dcc, Input, Output, State
import dash
import pandas as pd
from dash.dash_table import DataTable
from dataStore import data, playerMatchup

### TODO:
### - Make only score column clickable?
### - Make it clearer than the columns are clickable
### - Add a total under the player details table for both teams
### - Add logos?


def get_h2h_layout():
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

        html.Div(id="h2h-result"),

        html.Div(id="h2h-modal", style={"display": "none"}, children=[
            # Hidden close button, starts invisible, but Dash knows it exists
            html.Button("Close", id="close-h2h-modal", n_clicks=0, style={"display": "none"})
        ]),
        dcc.Store(id="selected-matchup", data={})
    ])

def register_h2h_callbacks(app):
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

        # Preparing data for h2h matchup table display
        # Removing Consolation matches from h2h history
        h2h_data = h2h_data[h2h_data["Type"] != "Consolation"]
        # Create the "Result" column
        h2h_data["Result"] = h2h_data["Win"].apply(lambda w: "W" if w == 1 else "L")
        # Create the "Score" column using team and opponent scores
        h2h_data["Score"] = h2h_data["Points For"].astype(int).astype(str) + " - " + h2h_data["Points Against"].astype(int).astype(str)

        # h2h_data["Score Button"] = h2h_data.apply(
        #     lambda row: html.Button(
        #         row["Score"],
        #         id={"type": "matchup-score-button", "index": f"{row['Year']}_{row['Week']}_{row['Team Name']}"}, 
        #         n_clicks=0
        #     ), axis=1
        # )

        columns_to_display = ["Year", "Week", "Team Name", "Type", "Result", "Score", "Opponent Team Name", "Opponent Owner"]
        #columns_to_display = ["Year", "Week", "Team Name", "Type", "Result", "Score Button", "Opponent Team Name", "Opponent Owner"]
        table_data = h2h_data[columns_to_display].sort_values(by=["Year", "Week"], ascending=[False, False])

        return html.Div([
            html.H3(f"{team1_name} vs. {team2_name}"),
            html.P(f"Overall Record: {int(total_wins)} - {int(total_losses)}"),
            html.P(f"Regular Season: {int(regular_wins)} - {int(regular_losses)}"),
            html.P(f"Playoffs: {int(playoff_wins)} - {int(playoff_losses)}"),
            html.Br(),
            html.H4("Matchup History"),
            dcc.Loading(
                children=[
                    DataTable(
                        id="h2h-table",
                        columns=[{"name": col, "id": col} for col in columns_to_display],
                        data=table_data.to_dict("records"),
                        active_cell=None,
                        style_table={"overflowX": "auto", "margin": "auto", "width": "80%"},
                        style_cell={"textAlign": "center", "padding": "5px"},
                        style_header={"backgroundColor": "rgb(30, 30, 30)", "color": "white"},
                        style_data_conditional=[
                            {
                                'if': {
                                    'filter_query': '{Type} = "Playoffs"'
                                },
                                'fontWeight': 'bold'
                            },
                            {
                                'if': {
                                    'column_id': 'Result',
                                    'filter_query': '{Result} = "W"'
                                },
                                'color': 'green'
                            },
                            {
                                'if': {
                                    'column_id': 'Result',
                                    'filter_query': '{Result} = "L"'
                                },
                                'color': 'red'
                            }
                        ],
                    )
                ],
                type="default"
            )
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
    
    @app.callback(
        Output("selected-matchup", "data"),
        Input("h2h-table", "active_cell"),
        State("h2h-table", "data"),
        prevent_initial_call=True
    )
    def handle_row_click(active_cell, table_data):
        if active_cell is None:
            return dash.no_update
        row_data = table_data[active_cell["row"]]
        return {
            "Year": row_data["Year"],
            "Week": row_data["Week"],
            "Team1": row_data["Team Name"],
            "Team2": row_data["Opponent Team Name"]
        }

    @app.callback(
        Output("h2h-modal", "style"),
        Output("h2h-modal", "children"),
        Input("selected-matchup", "data"),
        Input("h2h-team1-dropdown", "value"),
        Input("h2h-team2-dropdown", "value"),
        Input("close-h2h-modal", "n_clicks"),
        prevent_initial_call=True,
    )
    def toggle_modal(selected, team1_id, team2_id, close_click):
        ctx = dash.callback_context
        triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]

        # Close modal if dropdowns changed or close button clicked
        if triggered_id in ["h2h-team1-dropdown", "h2h-team2-dropdown", "close-h2h-modal"]:
            return {"display": "none"}, None

        if triggered_id == "selected-matchup" and selected:
            year = selected["Year"]
            week = selected["Week"]
            team1 = selected["Team1"]
            team2 = selected["Team2"]

            # Filter and sort by FPTS descending
            team1_players = playerMatchup[
                (playerMatchup["Year"] == year) &
                (playerMatchup["Week"] == week) &
                (playerMatchup["Team Name"] == team1)
            ][["Player Name", "FPTS"]].sort_values(by="FPTS", ascending=False).reset_index(drop=True)

            team2_players = playerMatchup[
                (playerMatchup["Year"] == year) &
                (playerMatchup["Week"] == week) &
                (playerMatchup["Team Name"] == team2)
            ][["Player Name", "FPTS"]].sort_values(by="FPTS", ascending=False).reset_index(drop=True)

            max_rows = max(len(team1_players), len(team2_players))

            # Explicitly set dtypes to match expected types
            empty_row_team1 = pd.DataFrame({
                "Player Name": [""],
                "FPTS": [None]
            }).astype({"Player Name": str, "FPTS": float})

            empty_row_team2 = pd.DataFrame({
                "Player Name": [""],
                "FPTS": [None]
            }).astype({"Player Name": str, "FPTS": float})

            # Add missing rows to match length
            while len(team1_players) < max_rows:
                team1_players = pd.concat([team1_players, empty_row_team1], ignore_index=True)

            while len(team2_players) < max_rows:
                team2_players = pd.concat([team2_players, empty_row_team2], ignore_index=True)

            table_rows = []
            for i in range(max_rows):
                row = html.Tr([
                    html.Td(team1_players.loc[i, "Player Name"]),
                    html.Td(f"{team1_players.loc[i, 'FPTS']:.2f}" if pd.notna(team1_players.loc[i, "FPTS"]) else ""),
                    html.Td(""),
                    html.Td(f"{team2_players.loc[i, 'FPTS']:.2f}" if pd.notna(team2_players.loc[i, "FPTS"]) else ""),
                    html.Td(team2_players.loc[i, "Player Name"]),
                ])
                table_rows.append(row)

            return (
                {"display": "block"},
                html.Div([
                    html.Div([
                        html.Button("Close", id="close-h2h-modal", n_clicks=0),
                        html.H4("Matchup Details"),
                        html.P(f"Year: {year} | Week: {week}"),
                        html.Br(),
                        html.Table([
                            html.Thead(html.Tr([
                                html.Th(team1, style={"width": "25%"}),
                                html.Th("FPTS", style={"width": "10%"}),
                                html.Th("", style={"width": "5%"}),  # Spacer
                                html.Th("FPTS", style={"width": "10%"}),
                                html.Th(team2, style={"width": "25%"})
                            ])),
                            html.Tbody(table_rows)
                        ], style={
                            "width": "100%",
                            "tableLayout": "fixed",
                            "textAlign": "center",
                            "margin": "auto",
                            "borderCollapse": "collapse",
                            "marginTop": "15px"
                        })
                    ], style={
                        "backgroundColor": "white",
                        "padding": "20px",
                        "borderRadius": "8px",
                        "width": "90%",
                        "maxWidth": "700px",
                        "margin": "auto",
                        "boxShadow": "0px 4px 12px rgba(0, 0, 0, 0.1)"
                    })
                ])
            )

        elif triggered_id == "close-h2h-modal":
            # Modal close: hide modal and keep the hidden button in children so it stays in DOM
            return (
                {"display": "none"},
                html.Button("Close", id="close-h2h-modal", n_clicks=0, style={"display": "none"})
            )

        raise dash.exceptions.PreventUpdate