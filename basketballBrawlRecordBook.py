import pandas as pd
from dash import html, dcc, dash_table, Output, Input
from dataStore import playerMatchup, playerDaily, data, activityData

### TODO:
### - Show how many players for each team under all nba teams
### - Show how many times each player scored more than 100 points under 100 point table
### - Clickable link to google search of 100 point games?
### - Real NBA statlines for 100 point games and negative games?
### - Add best draft pick
### - Add most improved award?

# Most points in a single matchup (Team)
top_team_game = data.sort_values("Points For", ascending=False).iloc[0]

# Most points in a single matchup (Player)
top_player_game = playerMatchup.sort_values("FPTS", ascending=False).iloc[0]

# Most points in a single day by a player
top_daily_game = playerDaily.sort_values("FPTS", ascending=False).iloc[0]

# All 100+ point daily games
hundred_point_games = playerDaily[playerDaily["FPTS"] >= 100].copy()
hundred_point_games.sort_values("Date", ascending=False, inplace=True)

# You can rename columns or format as needed
hundred_point_games = hundred_point_games[["Date", "Player Name", "Team Name", "FPTS"]]
hundred_point_games["Date"] = pd.to_datetime(hundred_point_games["Date"]).dt.strftime("%m/%d/%Y")

dropdown_options = [
    {"label": "All-Time", "value": "All-Time"}
] + [
    {"label": str(year), "value": str(year)}
    for year in sorted(playerMatchup["Year"].unique(), reverse=True)
]

def get_record_book_layout():
    return html.Div([
        html.H2("Record Book"),

        html.Div([
            html.Label("Select Year:"),
            dcc.Dropdown(
                id="award-year-dropdown",
                options=dropdown_options,
                value=str(playerMatchup["Year"].max()),  # Set to most recent year
                searchable=False,
                clearable=False
            )
        ], style={"marginBottom": "20px"}),

        html.Div(id="awards-display")
    ])


def register_record_book_callbacks(app):
    @app.callback(
        Output("awards-display", "children"),
        Input("award-year-dropdown", "value")
    )
    def update_awards_display(selected_year):
        if selected_year == "All-Time":
            transact_actions = ["WAIVER ADDED", "DROPPED", "DRAFTED", "TRADED"]
            transact_df = activityData[activityData["Action"].isin(transact_actions)]

            # Count total actions per player
            transaction_counts = (
                transact_df.groupby("Asset")["Action"]
                .count()
                .reset_index(name="Transaction Count")
                .sort_values("Transaction Count", ascending=False)
                .head(10)
            )


            return html.Div([
                html.H4("Most Points in a Single Matchup (Team)"),
                html.P(f"{top_team_game['Team Name']} scored {top_team_game['Points For']} points in Week {top_team_game['Week']} of {top_team_game['Year']}"),

                html.H4("Most Points in a Single Matchup (Player)"),
                html.P(f"{top_player_game['Player Name']} scored {top_player_game['FPTS']} points in Week {top_player_game['Week']} of {top_player_game['Year']} for {top_player_game['Team Name']}"),

                html.H4("Most Points in a Single Day (Player)"),
                html.P(f"{top_daily_game['Player Name']} scored {top_daily_game['FPTS']} points on {top_daily_game['Date']} for {top_daily_game['Team Name']}"),

                html.H4("Players with 100+ Point Days"),
                dash_table.DataTable(
                    columns=[
                        {"name": "Date", "id": "Date"},
                        {"name": "Player Name", "id": "Player Name"},
                        {"name": "Team Name", "id": "Team Name"},
                        {"name": "FPTS", "id": "FPTS"}
                    ],
                    data=hundred_point_games.to_dict("records"),
                    style_table={'overflowX': 'auto'},
                    style_cell={'textAlign': 'left'}
                ),

                html.H4("Players with Negative Point Days"),
                dash_table.DataTable(
                    columns=[
                        {"name": "Date", "id": "Date"},
                        {"name": "Player Name", "id": "Player Name"},
                        {"name": "Team Name", "id": "Team Name"},
                        {"name": "FPTS", "id": "FPTS"}
                    ],
                    data=playerDaily[
                        (playerDaily["FPTS"] < 0) & 
                        (~playerDaily["Player Slot"].isin(["BE", "IR"]))
                    ].sort_values("Date", ascending=False)[["Date", "Player Name", "Team Name", "FPTS"]]
                    .assign(Date=lambda df: pd.to_datetime(df["Date"]).dt.strftime("%m/%d/%Y"))
                    .to_dict("records"),
                    style_table={'overflowX': 'auto'},
                    style_cell={'textAlign': 'left'}
                ),

                html.H5("Top 10 Most Active Players (Total Transactions)"),
                dash_table.DataTable(
                    columns=[
                        {"name": "Player Name", "id": "Asset"},
                        {"name": "Transaction Count", "id": "Transaction Count"},
                    ],
                    data=transaction_counts.to_dict("records"),
                    style_table={'overflowX': 'auto'},
                    style_cell={'textAlign': 'left'}
                )
            ])
        
        selected_year = int(selected_year)
        year_df = playerMatchup[playerMatchup["Year"] == selected_year]

        # === MVP ===
        mvp_df = year_df.groupby("Player Name")["FPTS"].sum().reset_index()
        mvp = mvp_df.sort_values("FPTS", ascending=False).iloc[0]

        # === Expand positions ===
        # Build a dataframe: each row is a player/position combo with total FPTS
        position_rows = []
        grouped = year_df.groupby("Player Name")
        for player, group in grouped:
            total_fpts = group["FPTS"].sum()
            positions = set(group["Position"].dropna().unique()) | \
                        set(group["Position2"].dropna().unique()) | \
                        set(group["Position3"].dropna().unique())
            for pos in positions:
                position_rows.append({
                    "Player Name": player,
                    "Position": pos,
                    "FPTS": total_fpts
                })

        pos_df = pd.DataFrame(position_rows)
        pos_df = pos_df.sort_values("FPTS", ascending=False)

        # === Select top players per position, ensuring uniqueness ===
        def get_all_nba_team(pos_df, used_players):
            team = []
            for pos in ["G", "G", "F", "F", "C"]:
                positions = []
                if pos == "G":
                    positions = ["PG", "SG"]
                elif pos == "F":
                    positions = ["SF", "PF"]
                else:
                    positions = ["C"]
                eligible = pos_df[
                    pos_df["Position"].isin(positions) &
                    (~pos_df["Player Name"].isin(used_players))
                ]
                if not eligible.empty:
                    player_row = eligible.iloc[0]
                    player_name = player_row["Player Name"]

                    # Find latest team for this player
                    player_games = year_df[year_df["Player Name"] == player_name]
                    latest_game = player_games.sort_values("Week", ascending=False).iloc[0]
                    latest_team = latest_game["Team Name"]

                    team.append({
                        "Position": pos,
                        "Player": player_name,
                        "Team Name": latest_team,
                        "FPTS": player_row["FPTS"]
                    })
                    used_players.add(player_row["Player Name"])
            return team

        used_players = set()
        first_team = get_all_nba_team(pos_df, used_players)
        second_team = get_all_nba_team(pos_df, used_players)
        third_team = get_all_nba_team(pos_df, used_players)

        # === Return display content ===
        def make_team_table(team_data, label):
            return html.Div([
                html.H4(label),
                dash_table.DataTable(
                    columns=[
                        {"name": "Position", "id": "Position"},
                        {"name": "Player", "id": "Player"},
                        {"name": "Team Name", "id": "Team Name"},
                        {"name": "FPTS", "id": "FPTS"}
                    ],
                    data=team_data,
                    style_cell={"textAlign": "left"},
                )
            ])

        # === League Slut ===
        activity_year = activityData[activityData["Year"] == selected_year]
        slut_counts = activity_year.groupby("Asset")["Team ID"].nunique().reset_index()
        slut_counts.columns = ["Player Name", "Unique Teams"]
        max_teams = slut_counts["Unique Teams"].max()
        sluts = slut_counts[slut_counts["Unique Teams"] == max_teams]

        # Best Waiver Add per Year
        yearActivity = activityData[activityData["Year"] == selected_year]
        waiver_adds = yearActivity[yearActivity["Action"] == "WAIVER ADDED"].copy()

        waiver_adds.rename(columns={"Asset": "Player Name"}, inplace=True)

        # Remove duplicate adds by same team/player in a year
        waiver_adds = waiver_adds.drop_duplicates(subset=["Player Name", "Team Name"])

        year_totals = (
            year_df.groupby(["Player Name", "Team Name"])["FPTS"]
            .sum()
            .reset_index()
        )

        # Merge with player scores
        waiver_stats = waiver_adds.merge(
            year_totals, on=["Player Name", "Team Name"], how="left"
        )

        # Group by (Year, Player, Team) and sum points
        # waiver_points = waiver_stats.groupby(
        #     ["Player Name", "Team Name"]
        # )["FPTS"].sum().reset_index()

        #print(type(waiver_points))

        waiver_stats = waiver_stats.sort_values("FPTS", ascending=False).reset_index()

        # For each year, get player with max points
        best_waiver_add = waiver_stats.iloc[0]

        return html.Div([
            html.H3(f"{selected_year} Awards"),
            html.H4("\U0001F3C6 MVP"),
            html.P(f"{mvp['Player Name']} with {mvp['FPTS']} fantasy points"),
            make_team_table(first_team, "All-NBA 1st Team"),
            make_team_table(second_team, "All-NBA 2nd Team"),
            make_team_table(third_team, "All-NBA 3rd Team"),
            html.H4("Best Waiver Add"),
            html.P(
                f"{best_waiver_add['Player Name']} on {best_waiver_add['Team Name']} scored {best_waiver_add['FPTS']} points"
            ),
            html.H4("League Slut (Most Unique Teams in a Season)"),
            dash_table.DataTable(
                columns=[{"name": col, "id": col} for col in sluts.columns],
                data=sluts.to_dict("records"),
                style_cell={"textAlign": "left"},
            )
        ])
