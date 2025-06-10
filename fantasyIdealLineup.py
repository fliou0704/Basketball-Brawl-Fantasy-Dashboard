from espn_api.basketball import League
import pandas as pd


league_id = 609694684
swid = "{462737C8-F92F-4033-8AD6-1D877AC43C1D}"
espn_s2 = "AEAgnCeltBfv4nKLUgjlax5tsKzVho%2B6cA1L370VKGvF%2B8hlSX4dpV6Gv7kWYNR5t3zCcNNNwmdXlDPD3HMHLCK%2B6EjbZSYRcIKDl32HUTlKJYweuLKQkzjVDaj89PrtCQ6Cv5zujpbZo7SZ50hqICxorzGB3w01Tds62R78b4wQctPA8rL%2ByshLkXQXs9BM8f9ULC5JywoL3i%2B98bHo%2F9JzYyqmCdUvC1ugiM%2F5%2BY63l49PvhdpoEkbn340BC6gShqus0164TuLh28VviKz6JwKssbPorWtoA%2Fx5RhSs%2FLarA%3D%3D"
year = 2024

league = League(league_id=league_id, year=year, espn_s2=espn_s2, swid=swid)

eligiblePositions = ['PG', 'SG', 'SF', 'PF', 'C']

data = pd.read_csv('basketballBrawl - Sheet2.csv')

lineup = ['PG', 'SG', 'SF', 'PF', 'C', 'G', 'F', 'UTIL', 'UTIL2', 'UTIL3']

ideal_lineups = pd.DataFrame(columns = data.columns)

for week in range(1, 21):
    weekData = data[data['Week'] == week].copy()
    weekData = weekData.sort_values("FPTS")

    # Find the highest scoring player for each position
    selected_players = set()
    ideal_lineup = {}
    for position in lineup:
        if position in ['PG', 'SG', 'SF', 'PF', 'C']:
            # Filter for players who play the specified position
            position_players = weekData[(weekData['Position'] == position) | 
                                        (weekData['Position2'] == position) |
                                        (weekData['Position3'] == position)]
        elif position == "G":
            positions = ['PG', 'SG']
            position_players = weekData[(weekData['Position'].isin(positions)) | 
                                        (weekData['Position2'].isin(positions)) |
                                        (weekData['Position3'].isin(positions))]
        elif position == "F":
            positions = ['SF', 'PF']
            position_players = weekData[(weekData['Position'].isin(positions)) | 
                                        (weekData['Position2'].isin(positions)) |
                                        (weekData['Position3'].isin(positions))]
        else:
            position_players = weekData
        
        # Get the player with the highest FPTS in this position
        if not position_players.empty:
            top_player = position_players.loc[position_players['FPTS'].idxmax()]
            #ideal_lineup[position] = top_player[['Player Name', 'FPTS', 'Team Name']] # Select columns to keep in ideal lineup
            #ideal_lineup[position] = top_player.drop(columns=['Year', 'Team Name']) # Select columns to drop
            ideal_lineup[position] = top_player # Keep all columns

        # Add the selected player to the list of selected players
        weekData = weekData[weekData['Player Name'] != top_player['Player Name']]

    # Display the ideal lineup
    ideal_lineup_df = pd.DataFrame(ideal_lineup).T
    ideal_lineups = pd.concat([ideal_lineups, ideal_lineup_df])
    print("Best Possible Lineup for Week " + str(week))
    print(ideal_lineup_df)
    print('Total points: ' + str(sum(ideal_lineup_df['FPTS'])))

    print(ideal_lineups)

