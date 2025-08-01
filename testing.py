from espn_api.basketball import League
import pandas as pd

### TODO
### - Look into merging player dataset with basketball reference dataset to compare fantasy points and win share and/or usage
### - Look into merging player dataset with another player dataset to show unique stats about teams like height, weight, birhtplace, etc. 
### - Look into adding images to player dataset somehow
### - Playoff stats
### - Last week in review with team of the week, matchup of the week, highest scorers of week, etc

league_id = 609694684
swid = "{462737C8-F92F-4033-8AD6-1D877AC43C1D}"
espn_s2 = "AEAgnCeltBfv4nKLUgjlax5tsKzVho%2B6cA1L370VKGvF%2B8hlSX4dpV6Gv7kWYNR5t3zCcNNNwmdXlDPD3HMHLCK%2B6EjbZSYRcIKDl32HUTlKJYweuLKQkzjVDaj89PrtCQ6Cv5zujpbZo7SZ50hqICxorzGB3w01Tds62R78b4wQctPA8rL%2ByshLkXQXs9BM8f9ULC5JywoL3i%2B98bHo%2F9JzYyqmCdUvC1ugiM%2F5%2BY63l49PvhdpoEkbn340BC6gShqus0164TuLh28VviKz6JwKssbPorWtoA%2Fx5RhSs%2FLarA%3D%3D"
year = 2024

# espn_s2 = 'AEB%2BZ33nD3CVjTy1%2BY7Y6lYP5KSTfdAI6lUjIpSJ8WHLUyjlIMjYKiJlolvuDTyLPBjdhVHIE5UlyyOh6M%2BWtfB1WA5v2CtQhc1CVjmoF%2B%2BgYmTNE%2FDJgSUC0ws0N9S%2Bermktd4xrMRGnr6C%2FpE2hqqe%2BSjMMAVw941%2F%2BAqJw5qqPpT4LfO4BQuSGepw20APuVapbRM3uzCzqadS91HCK0%2BTQhEpm1lpVCGlqCx%2F6rb0UwYNqjJeLkbuXXbrkqK9mPrg5QAqGRI914K2U%2Bah2yD08dXZ8xfYB7K0ilPeqJPKJA%3D%3D'
# year = 2023

league = League(league_id=league_id, year=year, espn_s2=espn_s2, swid=swid)

scoringPeriods = int(league.scoringPeriodId)

df = pd.DataFrame(columns=["Year", "Scoring Period", "Date", "Team Name", "Player Name", "Player ID", "Player Slot", "FPTS"])

for sp in range(1, scoringPeriods + 1):
    for boxScore in league.box_scores(scoring_period=sp, matchup_total=False):

        for player in boxScore.home_lineup:

            played = False
            if bool(player.stats):
                day_stats = player.stats.get(str(sp))
                if day_stats and "total" in day_stats:
                    played = True

            if played:
                date_played = player.stats[str(sp)]["date"]
                if date_played:
                    date_played = date_played.date()
                print(player.name)
                minutes = player.stats[str(sp)]["total"].get("MIN", None)
                print(minutes)

# players = players[players["Year"] == 2025]
# players = players[players["Week"] < 21]
# players = players[players["Team Name"] == "The Bronx Orthodox Church"]
# print(players["FPTS"].sum())