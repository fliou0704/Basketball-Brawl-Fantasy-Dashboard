import os
import pandas as pd
from dash import Dash, html, dcc, Input, Output
from basketballBrawlHome import get_home_layout, register_home_callbacks
from basketballBrawlTeamStats import get_team_layout, create_team_difference_chart, create_team_pie_chart, create_positional_pie_chart, plot_player_pie_chart
from basketballBrawlHistoricalH2H import get_h2h_layout, register_h2h_callbacks

# Set suppress_callback_exceptions=True
app = Dash(__name__, suppress_callback_exceptions=True)

data = pd.read_csv("basketballBrawlLeagueData.csv")

register_home_callbacks(app, data)
register_h2h_callbacks(app, data)

# Define the layout with tabs
app.layout = html.Div([
    dcc.Tabs(id="tabs", value="home", children=[
        dcc.Tab(label="Home", value="home"),
        dcc.Tab(label="Team Stats", value="team"),
        dcc.Tab(label="Historical H2H", value="h2h")  # Add this line
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
        return get_home_layout(app, data)
    elif tab == "team":
        return get_team_layout()
    elif tab == "h2h":
        return get_h2h_layout(data) 

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
    port = int(os.environ.get("PORT", 8050))  # Use Render's port or default to 8050 locally
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False) # Set debug and use_reloader to False for deployment (Use Ctrl + C to shut down app locally)