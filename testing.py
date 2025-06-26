from espn_api.basketball import League
import pandas as pd

league_id = 609694684
swid = "{462737C8-F92F-4033-8AD6-1D877AC43C1D}"
espn_s2 = "AEAgnCeltBfv4nKLUgjlax5tsKzVho%2B6cA1L370VKGvF%2B8hlSX4dpV6Gv7kWYNR5t3zCcNNNwmdXlDPD3HMHLCK%2B6EjbZSYRcIKDl32HUTlKJYweuLKQkzjVDaj89PrtCQ6Cv5zujpbZo7SZ50hqICxorzGB3w01Tds62R78b4wQctPA8rL%2ByshLkXQXs9BM8f9ULC5JywoL3i%2B98bHo%2F9JzYyqmCdUvC1ugiM%2F5%2BY63l49PvhdpoEkbn340BC6gShqus0164TuLh28VviKz6JwKssbPorWtoA%2Fx5RhSs%2FLarA%3D%3D"
year = 2024

league = League(league_id=league_id, year=year, espn_s2=espn_s2, swid=swid)

#print(league.settings.matchup_periods)
mps = []
for mp in league.settings.matchup_periods:
    mps.append(mp)
print(mps[-1])

# df = pd.read_csv('data/basketballBrawlDailyPlayerData.csv')
# print(df[df["FPTS"] < 0])
# df = df[~df["Player Slot"].isin(["BE", "IR"])]


# df2024 = df[df["Year"] == 2024]
# print(df2024.groupby("Player Name")["FPTS"].sum().sort_values(ascending=False))

# players = pd.read_csv('data/basketballBrawlPlayerData.csv')
# print(players.groupby("Player Name")["FPTS"].sum().sort_values(ascending=False))
