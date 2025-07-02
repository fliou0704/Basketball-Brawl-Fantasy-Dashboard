from espn_api.basketball import League
import pandas as pd
from datetime import datetime

### TODO:
### - Figure out how to save old data without overwriting it
### - Filter out useless drops (end of season drops, weird Wemby Arian drop)


league_id = 609694684
swid = "{462737C8-F92F-4033-8AD6-1D877AC43C1D}"
espn_s2 = "AEAgnCeltBfv4nKLUgjlax5tsKzVho%2B6cA1L370VKGvF%2B8hlSX4dpV6Gv7kWYNR5t3zCcNNNwmdXlDPD3HMHLCK%2B6EjbZSYRcIKDl32HUTlKJYweuLKQkzjVDaj89PrtCQ6Cv5zujpbZo7SZ50hqICxorzGB3w01Tds62R78b4wQctPA8rL%2ByshLkXQXs9BM8f9ULC5JywoL3i%2B98bHo%2F9JzYyqmCdUvC1ugiM%2F5%2BY63l49PvhdpoEkbn340BC6gShqus0164TuLh28VviKz6JwKssbPorWtoA%2Fx5RhSs%2FLarA%3D%3D"

### DO NOT OVERWRITE OLD DATA
#years = [2023, 2024, 2025]
years = [2026]

#all_data = pd.DataFrame(columns = ["Year", "Date", "Time", "Team Name", "Action", "Asset"])
all_data = pd.read_csv("data/activityData.csv")

for year in years:

    if year == 2023:
        espn_s2 = 'AEB%2BZ33nD3CVjTy1%2BY7Y6lYP5KSTfdAI6lUjIpSJ8WHLUyjlIMjYKiJlolvuDTyLPBjdhVHIE5UlyyOh6M%2BWtfB1WA5v2CtQhc1CVjmoF%2B%2BgYmTNE%2FDJgSUC0ws0N9S%2Bermktd4xrMRGnr6C%2FpE2hqqe%2BSjMMAVw941%2F%2BAqJw5qqPpT4LfO4BQuSGepw20APuVapbRM3uzCzqadS91HCK0%2BTQhEpm1lpVCGlqCx%2F6rb0UwYNqjJeLkbuXXbrkqK9mPrg5QAqGRI914K2U%2Bah2yD08dXZ8xfYB7K0ilPeqJPKJA%3D%3D'
    else:
        espn_s2 = "AEAgnCeltBfv4nKLUgjlax5tsKzVho%2B6cA1L370VKGvF%2B8hlSX4dpV6Gv7kWYNR5t3zCcNNNwmdXlDPD3HMHLCK%2B6EjbZSYRcIKDl32HUTlKJYweuLKQkzjVDaj89PrtCQ6Cv5zujpbZo7SZ50hqICxorzGB3w01Tds62R78b4wQctPA8rL%2ByshLkXQXs9BM8f9ULC5JywoL3i%2B98bHo%2F9JzYyqmCdUvC1ugiM%2F5%2BY63l49PvhdpoEkbn340BC6gShqus0164TuLh28VviKz6JwKssbPorWtoA%2Fx5RhSs%2FLarA%3D%3D"

    league = League(league_id=league_id, year=year, espn_s2=espn_s2, swid=swid)

    draft_date_23 = "10/16/2022"
    draft_time_23 = "21:30"
    draft_date_24 = "10/22/2023"
    draft_time_24 = "18:00"
    draft_date_25 = "10/17/2024"
    draft_time_25 = "19:15"

    draft = league.draft
    for pick in draft:
        leagueActivityRow = pd.DataFrame()
        leagueActivityRow['Year'] = [year]
        if year == 2023:
            leagueActivityRow['Date'] = [draft_date_23]
            leagueActivityRow['Time'] = [draft_time_23]
        elif year == 2024:
            leagueActivityRow['Date'] = [draft_date_24]
            leagueActivityRow['Time'] = [draft_time_24]
        elif year == 2025:
            leagueActivityRow['Date'] = [draft_date_25]
            leagueActivityRow['Time'] = [draft_time_25]
        leagueActivityRow['Team Name'] = [pick.team.team_name]
        leagueActivityRow['Asset'] = [pick.playerName]
        if not pick.keeper_status:
            leagueActivityRow['Action'] = ["DRAFTED"]
        else:
            leagueActivityRow['Action'] = ["KEEPER"]
        if all_data.empty:
            all_data = leagueActivityRow
        else:
            all_data = pd.concat([all_data, leagueActivityRow], ignore_index=True)

    if year == 2023:
        continue

    leagueActivity = pd.DataFrame(columns = ['Year', 'Team Name', 'Action', 'Asset'])
    for act in league.recent_activity(5000):
        activityDate = datetime.fromtimestamp(act.date / 1000)

        leagueActivityRow = pd.DataFrame({"Datetime": [activityDate]})


        if act.actions != []:
            for transaction in act.actions:
                team = ''
                action = ''
                player = ''
                index = 0
                for item in transaction:
                    index += 1
                    if index == 1:
                        team = item
                    elif index == 2:
                        action = item
                    elif item != '':
                        player = item

                leagueActivityRow['Year'] = [year]
                leagueActivityRow['Team Name'] = [team.team_name]
                leagueActivityRow['Action'] = [action]
                leagueActivityRow['Asset'] = [player]

                leagueActivity = pd.concat([leagueActivity, leagueActivityRow])

    leagueActivity["Date"] = leagueActivity["Datetime"].dt.strftime("%m/%d/%Y")
    leagueActivity["Time"] = leagueActivity["Datetime"].dt.strftime("%H:%M")

    leagueActivity.drop(columns=["Datetime"])
    leagueActivity = leagueActivity[["Year", "Date", "Time", "Team Name", "Action", "Asset"]]

    if all_data.empty:
        all_data = leagueActivity
    else:
        all_data = pd.concat([all_data, leagueActivity], ignore_index=True)

### DO NOT ADD DUPLICATE DATA
#activityManual = pd.read_csv("data/activityManualData.csv")
#all_data = pd.concat([all_data, activityManual], ignore_index=True)

all_data["Datetime"] = pd.to_datetime(all_data["Date"] + " " + all_data["Time"], format="%m/%d/%Y %H:%M")
all_data = all_data.sort_values("Datetime", ascending=False).reset_index(drop=True)
all_data = all_data.drop(columns=["Datetime"]) 

all_data.to_csv("data/activityData.csv", index=False)