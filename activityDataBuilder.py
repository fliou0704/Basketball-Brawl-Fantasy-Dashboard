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
#all_data = pd.read_csv("data/activityData.csv")

# for year in years:

#     if year == 2023:
#         espn_s2 = 'AEB%2BZ33nD3CVjTy1%2BY7Y6lYP5KSTfdAI6lUjIpSJ8WHLUyjlIMjYKiJlolvuDTyLPBjdhVHIE5UlyyOh6M%2BWtfB1WA5v2CtQhc1CVjmoF%2B%2BgYmTNE%2FDJgSUC0ws0N9S%2Bermktd4xrMRGnr6C%2FpE2hqqe%2BSjMMAVw941%2F%2BAqJw5qqPpT4LfO4BQuSGepw20APuVapbRM3uzCzqadS91HCK0%2BTQhEpm1lpVCGlqCx%2F6rb0UwYNqjJeLkbuXXbrkqK9mPrg5QAqGRI914K2U%2Bah2yD08dXZ8xfYB7K0ilPeqJPKJA%3D%3D'
#     else:
#         espn_s2 = "AEAgnCeltBfv4nKLUgjlax5tsKzVho%2B6cA1L370VKGvF%2B8hlSX4dpV6Gv7kWYNR5t3zCcNNNwmdXlDPD3HMHLCK%2B6EjbZSYRcIKDl32HUTlKJYweuLKQkzjVDaj89PrtCQ6Cv5zujpbZo7SZ50hqICxorzGB3w01Tds62R78b4wQctPA8rL%2ByshLkXQXs9BM8f9ULC5JywoL3i%2B98bHo%2F9JzYyqmCdUvC1ugiM%2F5%2BY63l49PvhdpoEkbn340BC6gShqus0164TuLh28VviKz6JwKssbPorWtoA%2Fx5RhSs%2FLarA%3D%3D"

#     league = League(league_id=league_id, year=year, espn_s2=espn_s2, swid=swid)

#     draft_date_23 = "10/16/2022"
#     draft_time_23 = "21:30"
#     draft_date_24 = "10/22/2023"
#     draft_time_24 = "18:00"
#     draft_date_25 = "10/17/2024"
#     draft_time_25 = "19:15"

#     draft = league.draft
#     for pick in draft:
#         leagueActivityRow = pd.DataFrame()
#         leagueActivityRow['Year'] = [year]
#         if year == 2023:
#             leagueActivityRow['Date'] = [draft_date_23]
#             leagueActivityRow['Time'] = [draft_time_23]
#         elif year == 2024:
#             leagueActivityRow['Date'] = [draft_date_24]
#             leagueActivityRow['Time'] = [draft_time_24]
#         elif year == 2025:
#             leagueActivityRow['Date'] = [draft_date_25]
#             leagueActivityRow['Time'] = [draft_time_25]
#         leagueActivityRow['Team Name'] = [pick.team.team_name]
#         leagueActivityRow['Asset'] = [pick.playerName]
#         if not pick.keeper_status:
#             leagueActivityRow['Action'] = ["DRAFTED"]
#         else:
#             leagueActivityRow['Action'] = ["KEEPER"]
#         if all_data.empty:
#             all_data = leagueActivityRow
#         else:
#             all_data = pd.concat([all_data, leagueActivityRow], ignore_index=True)

#     if year == 2023:
#         continue

#     leagueActivity = pd.DataFrame(columns = ['Year', 'Team Name', 'Action', 'Asset'])
#     for act in league.recent_activity(5000):
#         activityDate = datetime.fromtimestamp(act.date / 1000)

#         leagueActivityRow = pd.DataFrame({"Datetime": [activityDate]})


#         if act.actions != []:
#             for transaction in act.actions:
#                 team = ''
#                 action = ''
#                 player = ''
#                 index = 0
#                 for item in transaction:
#                     index += 1
#                     if index == 1:
#                         team = item
#                     elif index == 2:
#                         action = item
#                     elif item != '':
#                         player = item

#                 leagueActivityRow['Year'] = [year]
#                 leagueActivityRow['Team Name'] = [team.team_name]
#                 leagueActivityRow['Action'] = [action]
#                 leagueActivityRow['Asset'] = [player]

#                 leagueActivity = pd.concat([leagueActivity, leagueActivityRow])

#     leagueActivity["Date"] = leagueActivity["Datetime"].dt.strftime("%m/%d/%Y")
#     leagueActivity["Time"] = leagueActivity["Datetime"].dt.strftime("%H:%M")

#     leagueActivity.drop(columns=["Datetime"])
#     leagueActivity = leagueActivity[["Year", "Date", "Time", "Team Name", "Action", "Asset"]]

#     if all_data.empty:
#         all_data = leagueActivity
#     else:
#         all_data = pd.concat([all_data, leagueActivity], ignore_index=True)

### DO NOT ADD DUPLICATE DATA
#activityManual = pd.read_csv("data/activityManualData.csv")
#all_data = pd.concat([all_data, activityManual], ignore_index=True)

# all_data["Datetime"] = pd.to_datetime(all_data["Date"] + " " + all_data["Time"], format="%m/%d/%Y %H:%M")
# all_data = all_data.sort_values("Datetime", ascending=False).reset_index(drop=True)
# all_data = all_data.drop(columns=["Datetime"]) 

# all_data.to_csv("data/activityData.csv", index=False)


###
### CODE TO FIX ONE-SIDED TRADES
###

# df = pd.read_csv("data/activityData.csv")
# year = 
# df = df[df["Year"] == year]

# # Standardize string fields
# df['Team Name'] = df['Team Name'].str.strip()
# df['Asset'] = df['Asset'].str.strip()
# df['Action'] = df['Action'].str.strip().str.upper()

# # Filter trades
# trade_df = df[df['Action'] == 'TRADED'].copy()

# # Identify unique trades by Year + Date + Time
# group_cols = ['Year', 'Date', 'Time']
# trade_groups = trade_df.groupby(group_cols)

# # List to collect new RECEIVED rows
# received_rows = []

# # Process each trade event
# for (year, date, time), group in trade_groups:
#     teams = group['Team Name'].unique()
#     if len(teams) != 2:
#         print(f"⚠️ Skipping trade at {date} {time} with {len(teams)} teams")
#         continue  # skip weird or incomplete trades

#     team_a, team_b = teams
#     # Get assets from each team
#     from_a = group[group['Team Name'] == team_a]['Asset'].tolist()
#     from_b = group[group['Team Name'] == team_b]['Asset'].tolist()

#     # Assets team_b receives from team_a
#     for asset in from_a:
#         received_rows.append({
#             "Year": year,
#             "Date": date,
#             "Time": time,
#             "Team Name": team_b,
#             "Asset": asset,
#             "Action": "RECEIVED"
#         })

#     # Assets team_a receives from team_b
#     for asset in from_b:
#         received_rows.append({
#             "Year": year,
#             "Date": date,
#             "Time": time,
#             "Team Name": team_a,
#             "Asset": asset,
#             "Action": "RECEIVED"
#         })

# # Append new rows to original DataFrame
# received_df = pd.DataFrame(received_rows)
# df_fixed = pd.concat([df, received_df], ignore_index=True)

# # Optional: sort chronologically
# df_fixed['Timestamp'] = pd.to_datetime(df_fixed['Date'] + " " + df_fixed['Time'])
# df_fixed = df_fixed.sort_values(by=['Year', 'Timestamp'])

# # Drop the helper column
# df_fixed = df_fixed.drop(columns='Timestamp')

# # Save fixed data
# df_fixed.to_csv("data/activityData.csv", index=False)


###
### CODE TO FIX PLAYERS WHO ARE NOT KEPT
###


# Load activity data
# df = pd.read_csv("data/activityDataManual.csv")
# df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
# df['Time'] = df['Time'].fillna("00:00")  # Fill missing times
# df['Action'] = df['Action'].str.upper().str.strip()
# df['Asset'] = df['Asset'].str.strip()

# # Exclude draft picks (anything with "Round Pick" in Asset)
# df = df[~df['Asset'].str.contains("ROUND PICK", case=False, na=False)]

# # Step 1: Identify draft dates and times per year
# drafts = df[df['Action'].isin(['DRAFTED', 'KEEPER'])].copy()
# drafts = drafts.sort_values(['Year', 'Date', 'Time'])
# draft_date_time_by_year = (
#     drafts.groupby('Year')
#     .agg({'Date': 'first', 'Time': 'first'})
#     .dropna()
#     .to_dict(orient='index')
# )

# # Step 2: Get the latest action per (Year, Team ID, Player)
# df_sorted = df.sort_values(by=['Year', 'Date', 'Time'])
# latest_actions = df_sorted.groupby(['Year', 'Team ID', 'Asset']).last().reset_index()

# # Step 3: Get keepers per (Year, Team ID)
# keepers = df[df['Action'] == 'KEEPER']
# keepers_lookup = keepers.groupby(['Year', 'Team ID'])['Asset'].apply(set).to_dict()

# # Step 4: NOT KEPT Logic
# valid_acquisition_actions = {"DRAFTED", "WAIVER ADDED", "RECEIVED"}
# not_kept_rows = []

# for _, row in latest_actions.iterrows():
#     year = row['Year']
#     team_id = row['Team ID']
#     player = row['Asset']
#     action = row['Action']

#     # Skip if last action was not valid for NOT KEPT
#     if action not in valid_acquisition_actions:
#         continue

#     next_year = year + 1
#     keeper_set = keepers_lookup.get((next_year, team_id), set())

#     # Skip if the next year's draft hasn't happened
#     if next_year not in draft_date_time_by_year:
#         continue

#     if player not in keeper_set:
#         draft_date = draft_date_time_by_year[next_year]['Date']
#         draft_time = draft_date_time_by_year[next_year]['Time']
#         team_name = row['Team Name']

#         not_kept_rows.append({
#             "Year": next_year,
#             "Date": draft_date,
#             "Time": draft_time,
#             "Team Name": team_name,
#             "Team ID": team_id,
#             "Asset": player,
#             "Action": "NOT KEPT"
#         })

# # Step 5: Combine and save
# not_kept_df = pd.DataFrame(not_kept_rows)
# final_df = pd.concat([df, not_kept_df], ignore_index=True)
# final_df = final_df.sort_values(by=["Year", "Date", "Time"], na_position='last')

# # Save
# final_df.to_csv("data/activityData_with_not_kept.csv", index=False)




###
### CODE TO ADD TEAM IDS TO ACTIVITY DATA
###

# df = pd.read_csv("data/activityData.csv")

# team_name_to_id = {
#     "Keegan It Real": 1,
#     "New Jersey Eren": 2,
#     "Pooh Shaisty": 12,
#     "Who Invited This Kid?": 7,
#     "Team Chigga": 5,
#     "Fordham Rams": 16,
#     "NYC Chopp Cheese": 16,
#     "Jalen Inc.": 16,
#     "Paulie Gee's": 8,
#     "The Bronx Orthodox Church": 13,
#     "NY L-Eat Gang": 10,
#     "For All the bullDawgs": 10,
#     "I Watch Basketbal": 17
# }

# # Add Team ID column using the mapping
# df['Team ID'] = df['Team Name'].map(team_name_to_id)

# # Check if any team names failed to map (missing from your dictionary)
# missing = df[df['Team ID'].isna()]['Team Name'].unique()
# if len(missing) > 0:
#     print("⚠️ The following team names are missing from your mapping dictionary:")
#     print(missing)
# else:
#     print("✅ All team names successfully mapped to Team IDs.")

# # Optional: save to a new CSV
# df.to_csv("data/activityData.csv", index=False)



### 
### Code for Adding Player IDs to activityData from playerMatchupData
###
# activityData = pd.read_csv("data/activityData.csv")
# playerMatchup_df = pd.read_csv("data/playerMatchupData.csv")

# # Example: from playerMatchup df or other reliable source
# player_ids = playerMatchup_df[["Player Name", "Player ID"]].drop_duplicates()

# activityData["Player Name"] = activityData["Asset"]

# activityData = pd.merge(activityData, player_ids, on="Player Name", how="left")

# unmatched = activityData[activityData["Player ID"].isna()]
# print(unmatched["Player Name"].unique())

# activityData = activityData.drop('Player Name', axis=1)

# activityData.to_csv("data/activityData.csv", index=False)