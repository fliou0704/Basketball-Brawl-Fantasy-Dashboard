from espn_api.basketball import League
import pandas as pd
from datetime import datetime

### - Ranking best free agency pickups by looking at player acquisition type

### espn_s2 for 2021-2023
# espn_s2 = 'AEB%2BZ33nD3CVjTy1%2BY7Y6lYP5KSTfdAI6lUjIpSJ8WHLUyjlIMjYKiJlolvuDTyLPBjdhVHIE5UlyyOh6M%2BWtfB1WA5v2CtQhc1CVjmoF%2B%2BgYmTNE%2FDJgSUC0ws0N9S%2Bermktd4xrMRGnr6C%2FpE2hqqe%2BSjMMAVw941%2F%2BAqJw5qqPpT4LfO4BQuSGepw20APuVapbRM3uzCzqadS91HCK0%2BTQhEpm1lpVCGlqCx%2F6rb0UwYNqjJeLkbuXXbrkqK9mPrg5QAqGRI914K2U%2Bah2yD08dXZ8xfYB7K0ilPeqJPKJA%3D%3D'

league_id = 609694684
swid = "{462737C8-F92F-4033-8AD6-1D877AC43C1D}"
espn_s2 = "AEAgnCeltBfv4nKLUgjlax5tsKzVho%2B6cA1L370VKGvF%2B8hlSX4dpV6Gv7kWYNR5t3zCcNNNwmdXlDPD3HMHLCK%2B6EjbZSYRcIKDl32HUTlKJYweuLKQkzjVDaj89PrtCQ6Cv5zujpbZo7SZ50hqICxorzGB3w01Tds62R78b4wQctPA8rL%2ByshLkXQXs9BM8f9ULC5JywoL3i%2B98bHo%2F9JzYyqmCdUvC1ugiM%2F5%2BY63l49PvhdpoEkbn340BC6gShqus0164TuLh28VviKz6JwKssbPorWtoA%2Fx5RhSs%2FLarA%3D%3D"
year = 2024

data = pd.read_csv('basketballBrawl - Sheet2.csv')
#print(data[data['FPTS'] >= 250])

league = League(league_id=league_id, year=year, espn_s2=espn_s2, swid=swid)



leagueActivity = pd.DataFrame(columns = ['Date and Time', 'Team', 'Action', 'Player'])
for act in league.recent_activity(5000):
    activityDate = datetime.fromtimestamp(act.date / 1000)

    formatted_date = activityDate.strftime('%m/%d/%Y %H:%M')

    leagueActivityRow = pd.DataFrame({'Date and Time': [formatted_date]})


    if act.actions != []:
        #print(act.actions)
        for transaction in act.actions:
            team = ''
            action = ''
            player = ''
            index = 0
            for item in transaction:
                index += 1
                if index == 1:
                    team = item.team_name
                elif index == 2:
                    action = item
                elif item != '':
                    player = item
            leagueActivityRow['Team'] = [team]
            leagueActivityRow['Action'] = [action]
            leagueActivityRow['Player'] = [player]
            #print(formatted_date + '  ' + team + ' ' + action + ': ' + player)
            leagueActivity = pd.concat([leagueActivity, leagueActivityRow])

#print(leagueActivity[leagueActivity['Player'] == 'Jaime Jaquez Jr.'])

#### Print all trades
# print(leagueActivity[leagueActivity['Action'] == 'TRADED'])

### Print players and number of different teams they have been on
noTradeActivity = leagueActivity[leagueActivity['Action'].isin(['WAIVER ADDED', 'DROPPED'])]
uniqueTeams = noTradeActivity.groupby('Player')['Team'].nunique().reset_index(name='Unique Teams').sort_values('Unique Teams', ascending = False)
# print(uniqueTeams[uniqueTeams['Unique Teams'] >= 3])

### Print players and number of times they have been added, desceneding
# leagueActivity = leagueActivity[leagueActivity['Action'] == 'WAIVER ADDED']
# leagueActivity = leagueActivity.groupby('Player').size().reset_index(name='Add Count').sort_values('Add Count', ascending = False)
# print(leagueActivity[leagueActivity['Add Count'] >= 3])
# print(leagueActivity.groupby('Player').count().sort_values('Action', ascending = False))

### Print players who were picked up in order of FPTS they scored this year, filter by FPTS >= 1000

totalData = data.groupby('Player Name')['FPTS'].sum().reset_index()

switchedTeams = uniqueTeams[uniqueTeams['Unique Teams'] >= 2]
switchedTeamsActivity = noTradeActivity
remove = []
for index, row in switchedTeamsActivity.iterrows():
    if row['Player'] not in switchedTeams['Player'].tolist():
        remove.append(row['Player'])

for player in remove:
    switchedTeamsActivity = switchedTeamsActivity[switchedTeamsActivity['Player'] != player]

#print(switchedTeamsActivity)

addActivity = leagueActivity[leagueActivity['Action'] == 'WAIVER ADDED']
addActivity = addActivity[addActivity['Player'] != 'Victor Wembanyama'] # Remove Wemby since Arian added him as a joke
addActivity.rename(columns={'Player': 'Player Name'}, inplace=True)

pickupStats = addActivity.merge(totalData, on='Player Name', how='inner')
pickupStats = pickupStats[pickupStats['FPTS'] >= 1000]
#print(pickupStats.sort_values('FPTS', ascending = False))

### Print players who were picked up in order of FPTS they scored this year, filter by FPTS >= 1000
dropActivity = switchedTeamsActivity[switchedTeamsActivity['Action'] == 'DROPPED']
print(dropActivity[dropActivity['Player'] == 'Miles Bridges'])
dropActivity = dropActivity[dropActivity['Player'] != 'Victor Wembanyama'] # Remove Wemby since Arian added him as a joke
dropActivity.rename(columns={'Player': 'Player Name'}, inplace=True)

dropStats = dropActivity.merge(totalData, on='Player Name', how='inner')
dropStats = dropStats[dropStats['FPTS'] >= 1000]
print(dropStats.sort_values('FPTS', ascending = False))