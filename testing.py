from espn_api.basketball import League
import pandas as pd
from datetime import datetime
import numpy as np
import pprint, sys

### TODO
### - Look into merging player dataset with basketball reference dataset to compare fantasy points and win share and/or usage
### - Look into merging player dataset with another player dataset to show unique stats about teams like height, weight, birhtplace, etc. 
### - Look into adding images to player dataset somehow
### - Playoff stats
### - Last week in review with team of the week, matchup of the week, highest scorers of week, etc

data = pd.read_csv("data/basketballBrawlLeagueData.csv")

print(data[data["Team Name"] == "NY L-Eat Gang"])

print(data[(data["Team Name"] == "For All the bullDawgs") & (data["Year"] == 2024)])

