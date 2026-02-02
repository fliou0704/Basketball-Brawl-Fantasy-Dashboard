from dash import html, dcc, Input, Output, callback
from dash.dash_table import DataTable
import pandas as pd
import plotly.express as px
from dataStore import data, get_logo_path, get_team_color
import plotly.graph_objects as go
import base64
from pathlib import Path

### TODO
### - Fix team logos to have transparent backgrounds
### - Highest scoring player per week?

years = []
latestYear = -1

def get_home_layout(app):
    years = sorted(data['Year'].unique())
    years.sort(reverse=True)
    latestYear = max(years)
    
    return html.Div([
        html.H1("Basketball Brawl Dashboard", style={'textAlign': 'center', 'margin': '20px 0'}),
        
        html.Div([
            html.Label("Select Year:"),
            dcc.Dropdown(
                id="year-dropdown",
                options=[{"label": str(year), "value": year} for year in years],
                value=latestYear,
                clearable=False,
                searchable=False
            ),
        ], style={'width': '30%', 'margin': 'auto'}),

        html.Div(id="homepage-content")  # This gets populated by the callback
    ])

def register_home_callbacks(app):
    @app.callback(
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

        table_data["Team"] = table_data.apply(
            lambda row: f'<img src="{get_logo_path(row["Team Name"])}" style="height:20px; vertical-align:middle; margin-right:10px;">{row["Team Name"]}',
            axis=1
        )

        #table_data = table_data[['Rank', 'Team', 'Record', 'Cumulative Points For', 'Cumulative Points Against']]
        table_data = table_data.sort_values(by='Rank')

        # Build html.Table rows
        table_header = html.Tr([
            html.Th("Rank"),
            html.Th("Team"),
            html.Th("Record"),
            html.Th("Cumulative Points For"),
            html.Th("Cumulative Points Against")
        ])

        table_rows = []
        for _, row in table_data.iterrows():
            logo_img = html.Img(
                src=get_logo_path(row["Team Name"]),
                style={"height": "25px", "verticalAlign": "middle", "marginRight": "10px"}
            )
            team_cell = html.Td([
                logo_img,
                html.Span(row["Team Name"], style={"verticalAlign": "middle", "fontWeight": "bold"})
            ], style={"display": "flex", "alignItems": "center"})

            table_rows.append(html.Tr([
                html.Td(row["Rank"]),
                team_cell,
                html.Td(row["Record"]),
                html.Td(row["Cumulative Points For"]),
                html.Td(row["Cumulative Points Against"])
            ]))

        # Wrap in html.Table
        custom_table = html.Table(
            children=[table_header] + table_rows,
            style={
                "width": "80%",
                "margin": "auto",
                "borderCollapse": "collapse",
                "textAlign": "center"
            }
        )

        # Build Team Name ➝ Team ID mapping (based on latest team IDs from data)
        team_name_to_id = (
            yearData
            .drop_duplicates(subset="Team Name", keep="last")
            .set_index("Team Name")["Team ID"]
            .to_dict()
        )

        # Now build color map: Team Name ➝ Color
        color_map = {
            team_name: get_team_color(team_name_to_id.get(team_name))
            for team_name in yearData["Team Name"].unique()
        }

        ### Rank Progression Graph
        fig_rank_progression = px.line(
            yearData,
            x='Week',
            y='Rank',
            color='Team Name',
            title=f"Team Rank Progression - {selected_year}",
            markers=True,
            color_discrete_map=color_map
        )

        ### Rank Progression y-axis adjustment
        fig_rank_progression.update_yaxes(
            autorange="reversed",
            title="Rank",
            tickmode="linear",
            tick0=1,
            dtick=1  # show ticks at 1, 2, ..., 10
        )

        last_week = 23
        if selected_year == 2023:
            last_week = 24

        ### Rank Progression x-axis adjustment
        fig_rank_progression.update_xaxes(
            title="Week",
            tickmode="linear",
            tick0=1,
            dtick=1,  # show ticks at 1, 2, ..., latest_regular_week
            range=[0.5, last_week + 0.5]
        )

        ### Adding logos for last point on rank progression graph

        latestWeekData = yearData[yearData["Week"] == latest_week]
        x_vals = latestWeekData["Week"]
        y_vals = latestWeekData["Rank"]
        team_names = latestWeekData["Team Name"]

        # add logos
        for x, y, team in zip(x_vals, y_vals, team_names):
            logo = get_logo_base64(team)

            fig_rank_progression.add_layout_image(
                dict(
                    source=logo,
                    x=x,
                    y=y,
                    xref="x",
                    yref="y",
                    sizex=1,
                    sizey=1,
                    xanchor="center",
                    yanchor="middle",
                    layer="above"
                )
            )

        highest_scoring_teams = regularData.loc[regularData.groupby('Week')['Points For'].idxmax()]

        fig_highest_scoring = px.bar(
            highest_scoring_teams,
            x='Week',
            y='Points For',
            color='Team Name',
            title=f"Highest Scoring Team Each Week - {selected_year}",
            text='Team Abbreviation',
            color_discrete_map=color_map
        )
        fig_highest_scoring.update_traces(textposition='outside')

        last_regular_week = 20
        if selected_year == 2023:
            last_regular_week = 21

        fig_highest_scoring.update_xaxes(
            tick0=1,
            dtick=1,  # show ticks at 1, 2, ..., latest_regular_week
            range=[0.5, last_regular_week + 0.5]
        )

        fig_highest_scoring.update_yaxes(
            range=[0, highest_scoring_teams["Points For"].max() + 200]
        )

        return html.Div([
            custom_table,
            dcc.Graph(figure=fig_rank_progression),
            dcc.Graph(figure=fig_highest_scoring)
        ])
    
def get_logo_base64(team_name):
    path = Path("assets") / "logos" / Path(get_logo_path(team_name)).name
    if not path.exists():
        return None

    encoded = base64.b64encode(path.read_bytes()).decode()
    return f"data:image/png;base64,{encoded}"