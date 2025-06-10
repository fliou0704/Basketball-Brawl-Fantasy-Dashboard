from dash import Dash, html, dcc, Input, Output
from basketballBrawlHome import get_home_layout
from basketballBrawlTeamStats import get_team_layout, create_team_difference_chart, create_team_pie_chart, create_positional_pie_chart, plot_player_pie_chart

# Set suppress_callback_exceptions=True
app = Dash(__name__, suppress_callback_exceptions=True)

# Define the layout with tabs
app.layout = html.Div([
    dcc.Tabs(id="tabs", value="home", children=[
        dcc.Tab(label="Home", value="home"),
        dcc.Tab(label="Team Stats", value="team"),
    ]),
    html.Div(id="content")  # This will hold the content of the selected tab
])


# Callback to update the content based on selected tab
@app.callback(
    Output("content", "children"),
    [Input("tabs", "value")]
)
def render_content(tab):
    if tab == "home":
        return get_home_layout()
    elif tab == "team":
        return get_team_layout()

# Callback to update team name based on selected team in the dropdown
@app.callback(
    Output("team-name-display", "children"),
    Input("team-dropdown", "value")
)
def update_team_name(selected_team):
    if selected_team is None:
        return "Please select a team"
    
    # Generate the bar chart for the selected team
    team_difference_chart = create_team_difference_chart(selected_team)
    team_pie_chart = create_team_pie_chart(selected_team)
    positional_pie_chart = create_positional_pie_chart(selected_team)
    player_pie_chart = plot_player_pie_chart(selected_team)

    # Return the layout with the team name and chart
    return html.Div([
        html.H3(f"Selected Team: {selected_team}"),
        dcc.Graph(figure=team_difference_chart),
        dcc.Graph(figure=team_pie_chart),
        dcc.Graph(figure=positional_pie_chart),
        dcc.Graph(figure=player_pie_chart)
    ])

if __name__ == "__main__":
    app.run_server(debug=True)