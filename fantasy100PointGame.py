from espn_api.basketball import League
import pandas as pd
from datetime import datetime
import time

### - Highlight best (>=300 or 250) and worst (<= 0) weekly player performances on a team, also, flat out best and worst performances for each team
### - Possible way to find and showcase all single game 100 point fantasy performances




### espn_s2 for 2021-2023
# espn_s2 = 'AEB%2BZ33nD3CVjTy1%2BY7Y6lYP5KSTfdAI6lUjIpSJ8WHLUyjlIMjYKiJlolvuDTyLPBjdhVHIE5UlyyOh6M%2BWtfB1WA5v2CtQhc1CVjmoF%2B%2BgYmTNE%2FDJgSUC0ws0N9S%2Bermktd4xrMRGnr6C%2FpE2hqqe%2BSjMMAVw941%2F%2BAqJw5qqPpT4LfO4BQuSGepw20APuVapbRM3uzCzqadS91HCK0%2BTQhEpm1lpVCGlqCx%2F6rb0UwYNqjJeLkbuXXbrkqK9mPrg5QAqGRI914K2U%2Bah2yD08dXZ8xfYB7K0ilPeqJPKJA%3D%3D'

league_id = 609694684
swid = "{462737C8-F92F-4033-8AD6-1D877AC43C1D}"
espn_s2 = "AEAgnCeltBfv4nKLUgjlax5tsKzVho%2B6cA1L370VKGvF%2B8hlSX4dpV6Gv7kWYNR5t3zCcNNNwmdXlDPD3HMHLCK%2B6EjbZSYRcIKDl32HUTlKJYweuLKQkzjVDaj89PrtCQ6Cv5zujpbZo7SZ50hqICxorzGB3w01Tds62R78b4wQctPA8rL%2ByshLkXQXs9BM8f9ULC5JywoL3i%2B98bHo%2F9JzYyqmCdUvC1ugiM%2F5%2BY63l49PvhdpoEkbn340BC6gShqus0164TuLh28VviKz6JwKssbPorWtoA%2Fx5RhSs%2FLarA%3D%3D"
year = 2024

data = pd.read_csv('basketballBrawl - Sheet2.csv')
print(data[data['FPTS'] >= 300][['Week', 'Team Name', 'Player Name', 'FPTS']])

league = League(league_id=league_id, year=year, espn_s2=espn_s2, swid=swid)

#print(league.player_info("Nikola Jokic").stats)

#formula
#fpts = pts + reb + 3pm + ftm - fta - fga + (fgm * 2) + (blk * 4) + (stl * 4) + (ast * 2) - (to * 2)


# for team in league.teams:
#     for player in team.roster:
#         for attempt in range(5):
#             try:
#                 player_info = league.player_info(player.name).stats
#                 break
#             except ConnectionError:
#                 time.sleep(60)
#         for key in player_info:
#             try:
#                 if key == '2024_projected' or key == '2024_total':
#                     continue
#                 else:
#                     stats = player_info[key]['total']
#                     fant = stats['PTS'] + stats['REB'] + stats['3PM'] + stats['FTM'] - stats['FTA'] - stats['FGA'] + (stats['FGM'] * 2) + (stats['BLK'] * 4) + (stats['STL'] * 4) + (stats['AST'] * 2) - (stats['TO'] * 2)
#                     if fant >= 100:
#                         date = player_info[key]['date'].strftime('%m/%d/%Y %H:%M')
#                         print(date + " " + player.name + ': ' + str(fant))
#             except KeyError:
#                 continue