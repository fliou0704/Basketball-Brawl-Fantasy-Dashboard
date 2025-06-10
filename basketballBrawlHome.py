from dash import html, dcc
from dash.dash_table import DataTable
import pandas as pd
import plotly.express as px

def get_home_layout():
    # Load your data
    data = pd.read_csv("basketballBrawl2024.csv")  # Replace with your actual data file path


    latest_week = data['Week'].max()

    ranks = data[(data['Week'] == latest_week)][['Team Name', 'Rank']]

    regularData = data[data['Type'] == 'Regular']
    # Filter for the most recent week
    latest_regular_week = regularData['Week'].max()
    #recentRanks = regularData[regularData['Week'] == latest_week]['Rank']

    recentData = regularData[regularData['Week'] == latest_regular_week].copy()

    # Create a new column for 'Record' as '[Cumulative Wins] - [Cumulative Losses]'
    recentData['Record'] = recentData['Cumulative Wins'].astype(str) + " - " + recentData['Cumulative Losses'].astype(str)

    # Select the columns you need for the table display
    table_data = recentData[['Team Name', 'Record', 'Cumulative Points For', 'Cumulative Points Against']]

    table_data = table_data.merge(ranks, on='Team Name')

    table_data = table_data[['Rank', 'Team Name', 'Record', 'Cumulative Points For', 'Cumulative Points Against']]

    # Create the line plot for team ranks over time
    fig_rank_progression = px.line(
        regularData,
        x='Week',
        y='Rank',
        color='Team Name',
        title="Team Rank Progression Over the Season",
        markers=True
    )
    fig_rank_progression.update_yaxes(autorange="reversed", title="Rank")  # Invert y-axis so that 1 is at the top

    # Create the line plot for cumulative points over time
    fig_points_progression = px.line(
        regularData,
        x='Week',
        y='Cumulative Points For',
        color='Team Name',
        title="Cumulative Points For Over the Season",
        markers=True
    )
    fig_points_progression.update_yaxes(title="Total Points For")

    # Find the highest scoring team for each week
    highest_scoring_teams = regularData.loc[regularData.groupby('Week')['Points For'].idxmax()]

    # Create the bar plot for highest scoring team each week
    fig_highest_scoring = px.bar(
        highest_scoring_teams,
        x='Week',
        y='Points For',
        color='Team Name',
        title="Highest Scoring Team Each Week",
        labels={'Points For': 'Points For', 'Team Name': 'Team'},
        text='Team Name'
    )
    fig_highest_scoring.update_traces(textposition='outside')

    # Sort by 'Rank' in ascending order
    table_data = table_data.sort_values(by='Rank', ascending=True)

    # Title for the page
    title = html.H1("Basketball Brawl 2024", style={'textAlign': 'center', 'margin': '20px 0'})

    # Create the DataTable
    table = DataTable(
        columns=[
            {"name": "Rank", "id": "Rank"},
            {"name": "Team Name", "id": "Team Name"},
            {"name": "Record", "id": "Record"},
            {"name": "Cumulative Points For", "id": "Cumulative Points For"},
            {"name": "Cumulative Points Against", "id": "Cumulative Points Against"}
        ],
        data=table_data.to_dict('records'),  # Convert dataframe to dictionary format
        style_table={'width': '80%', 'margin': 'auto'},
        style_header={'backgroundColor': 'rgb(30, 30, 30)', 'color': 'white'},
        style_cell={'textAlign': 'center', 'padding': '10px'}
    )

    # Combine title and table in a layout
    layout = html.Div([
        title,
        table,
        dcc.Graph(figure=fig_rank_progression),
        dcc.Graph(figure=fig_points_progression),
        dcc.Graph(figure=fig_highest_scoring)
    ])
    
    return layout