from dash import html, dcc, Input, Output, callback
from dash.dash_table import DataTable
import pandas as pd
import plotly.express as px

### TODO:
### - Make team colors on graph consistent throughout the years.
### - Put team abbreviation above bars on highest scoring team each week graph instead of full team names.


data = pd.read_csv("basketballBrawlLeagueData.csv")
years = sorted(data['Year'].unique())
latestYear = max(years)

def get_home_layout(app):
    return html.Div([
        html.H1("Basketball Brawl Dashboard", style={'textAlign': 'center', 'margin': '20px 0'}),
        
        html.Div([
            html.Label("Select Year:"),
            dcc.Dropdown(
                id="year-dropdown",
                options=[{"label": str(year), "value": year} for year in years],
                value=latestYear,
                clearable=False
            ),
        ], style={'width': '30%', 'margin': 'auto'}),

        html.Div(id="homepage-content")  # This gets populated by the callback
    ])

@callback(
    Output("homepage-content", "children"),
    Input("year-dropdown", "value")
)
def update_homepage_content(selected_year):
    yearData = data[data["Year"] == selected_year]

    latest_week = yearData['Week'].max()
    ranks = yearData[yearData['Week'] == latest_week][['Team Name', 'Rank']]

    regularData = yearData[yearData['Type'] == 'Regular']
    latest_regular_week = regularData['Week'].max()
    recentData = regularData[regularData['Week'] == latest_regular_week].copy()

    recentData['Record'] = recentData['Cumulative Wins'].astype(str) + " - " + recentData['Cumulative Losses'].astype(str)

    table_data = recentData[['Team Name', 'Record', 'Cumulative Points For', 'Cumulative Points Against']]
    table_data = table_data.merge(ranks, on='Team Name', how='left')
    table_data = table_data[['Rank', 'Team Name', 'Record', 'Cumulative Points For', 'Cumulative Points Against']]
    table_data = table_data.sort_values(by='Rank')

    table = DataTable(
        columns=[{"name": col, "id": col} for col in table_data.columns],
        data=table_data.to_dict('records'),
        style_table={'width': '80%', 'margin': 'auto'},
        style_header={'backgroundColor': 'rgb(30, 30, 30)', 'color': 'white'},
        style_cell={'textAlign': 'center', 'padding': '10px'}
    )

    ### Rank Progression Graph
    fig_rank_progression = px.line(
        yearData,
        x='Week',
        y='Rank',
        color='Team Name',
        title=f"Team Rank Progression - {selected_year}",
        markers=True
    )

    ### Rank Progression y-axis adjustment
    fig_rank_progression.update_yaxes(
        autorange="reversed",
        title="Rank",
        tickmode="linear",
        tick0=1,
        dtick=1  # show ticks at 1, 2, ..., 10
    )

    ### Rank Progression x-axis adjustment
    fig_rank_progression.update_xaxes(
        title="Week",
        tickmode="linear",
        tick0=1,
        dtick=1,  # show ticks at 1, 2, ..., latest_regular_week
        range=[0.5, latest_week + 0.5]
    )

    fig_points_progression = px.line(
        regularData,
        x='Week',
        y='Cumulative Points For',
        color='Team Name',
        title=f"Cumulative Points For - {selected_year}",
        markers=True
    )
    fig_points_progression.update_yaxes(title="Total Points For")

    highest_scoring_teams = regularData.loc[regularData.groupby('Week')['Points For'].idxmax()]

    fig_highest_scoring = px.bar(
        highest_scoring_teams,
        x='Week',
        y='Points For',
        color='Team Name',
        title=f"Highest Scoring Team Each Week - {selected_year}",
        text='Team Name'
    )
    fig_highest_scoring.update_traces(textposition='outside')

    return html.Div([
        table,
        dcc.Graph(figure=fig_rank_progression),
        dcc.Graph(figure=fig_points_progression),
        dcc.Graph(figure=fig_highest_scoring)
    ])