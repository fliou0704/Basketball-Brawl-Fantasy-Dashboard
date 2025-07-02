from espn_api.basketball import League
import pandas as pd
from datetime import datetime
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials

### - Projected points at start of season vs. end of season results

### TODO
### - Print top players who outperformed their projections

### espn_s2 for 2021-2023
# espn_s2 = 'AEB%2BZ33nD3CVjTy1%2BY7Y6lYP5KSTfdAI6lUjIpSJ8WHLUyjlIMjYKiJlolvuDTyLPBjdhVHIE5UlyyOh6M%2BWtfB1WA5v2CtQhc1CVjmoF%2B%2BgYmTNE%2FDJgSUC0ws0N9S%2Bermktd4xrMRGnr6C%2FpE2hqqe%2BSjMMAVw941%2F%2BAqJw5qqPpT4LfO4BQuSGepw20APuVapbRM3uzCzqadS91HCK0%2BTQhEpm1lpVCGlqCx%2F6rb0UwYNqjJeLkbuXXbrkqK9mPrg5QAqGRI914K2U%2Bah2yD08dXZ8xfYB7K0ilPeqJPKJA%3D%3D'

league_id = 609694684
swid = "{462737C8-F92F-4033-8AD6-1D877AC43C1D}"
espn_s2 = "AEAgnCeltBfv4nKLUgjlax5tsKzVho%2B6cA1L370VKGvF%2B8hlSX4dpV6Gv7kWYNR5t3zCcNNNwmdXlDPD3HMHLCK%2B6EjbZSYRcIKDl32HUTlKJYweuLKQkzjVDaj89PrtCQ6Cv5zujpbZo7SZ50hqICxorzGB3w01Tds62R78b4wQctPA8rL%2ByshLkXQXs9BM8f9ULC5JywoL3i%2B98bHo%2F9JzYyqmCdUvC1ugiM%2F5%2BY63l49PvhdpoEkbn340BC6gShqus0164TuLh28VviKz6JwKssbPorWtoA%2Fx5RhSs%2FLarA%3D%3D"
year = 2024

data = pd.read_csv('basketballBrawl - Sheet2.csv')

league = League(league_id=league_id, year=year, espn_s2=espn_s2, swid=swid)

df = pd.DataFrame(columns = ['Team', 'Player', 'Projected', 'Actual', 'Difference'])

for team in league.teams:
    for player in team.roster:
        for attempt in range(5):
            try:
                player_info = league.player_info(player.name).stats
                break
            except ConnectionError:
                time.sleep(60)
        projected = 0
        total = 0
        totalCollected = False
        projectedCollected = False
        for key in player_info:
            try:
                if key == '2024_projected':
                    stats = player_info[key]['total']
                    # if player.name in ['Rudy Gobert', 'Walker Kessler']:
                    #     print(player_info)
                    projected = stats['PTS'] + stats['REB'] + stats['3PM'] + stats['FTM'] - stats['FTA'] - stats['FGA'] + (stats['FGM'] * 2) + (stats['BLK'] * 4) + (stats['STL'] * 4) + (stats['AST'] * 2) - (stats['TO'] * 2)
                    projectedCollected = True
                elif key == '2024_total':
                    stats = player_info[key]['total']
                    total = stats['PTS'] + stats['REB'] + stats['3PM'] + stats['FTM'] - stats['FTA'] - stats['FGA'] + (stats['FGM'] * 2) + (stats['BLK'] * 4) + (stats['STL'] * 4) + (stats['AST'] * 2) - (stats['TO'] * 2)
                    totalCollected = True
                else:
                    continue
                if projectedCollected and totalCollected:
                    difference = total - projected
                    df_row = pd.DataFrame({'Team': [team.team_name], 'Player': [player.name], 'Projected': [projected], 'Actual': [total], 'Difference': [difference]})
                    df = pd.concat([df, df_row])
                    break
            except KeyError:
                continue

df = df.reset_index(drop = True) # Gets rid of indices

df.to_csv('projectedVsActual.csv')

