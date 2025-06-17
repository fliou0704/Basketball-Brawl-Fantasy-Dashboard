import pandas as pd

data = pd.read_csv("basketballBrawlLeagueData.csv")
print((len(data[data["Year"] == 2024]) + 2) / 10)

data = data[data["Year"] == 2024]
week23 = data[data["Week"] == 23]
print(data[data["Week"] == 23])
print(week23["Team Name"])
