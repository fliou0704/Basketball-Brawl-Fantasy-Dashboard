from espn_api.basketball import League
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

#import sys
#print(sys.path)

league_id = 609694684
swid = "{462737C8-F92F-4033-8AD6-1D877AC43C1D}"
espn_s2 = "AEAgnCeltBfv4nKLUgjlax5tsKzVho%2B6cA1L370VKGvF%2B8hlSX4dpV6Gv7kWYNR5t3zCcNNNwmdXlDPD3HMHLCK%2B6EjbZSYRcIKDl32HUTlKJYweuLKQkzjVDaj89PrtCQ6Cv5zujpbZo7SZ50hqICxorzGB3w01Tds62R78b4wQctPA8rL%2ByshLkXQXs9BM8f9ULC5JywoL3i%2B98bHo%2F9JzYyqmCdUvC1ugiM%2F5%2BY63l49PvhdpoEkbn340BC6gShqus0164TuLh28VviKz6JwKssbPorWtoA%2Fx5RhSs%2FLarA%3D%3D"
year = 2024

league = League(league_id=league_id, year=year, espn_s2=espn_s2, swid=swid)



df = pd.DataFrame(columns=["Year", "Week", "Team Name", "Player Name", "Pro Team", "FPTS", "Position", "Position2", "Position3", "FTA", "PTS", "3PM", "BLK", "STL", "AST", "REB", "TO", "FGM", "FGA", "FTM"])

eligiblePositions = ['PG', 'SG', 'SF', 'PF', 'C']

for week in range(1, 21):
    for boxScore in league.box_scores(week):
        #print(boxScore.home_team.team_name, boxScore.home_score)
        for player in boxScore.home_lineup:
            df_row = pd.DataFrame({"Year": [year], "Week": [week], "Team Name": [boxScore.home_team.team_name], "Player Name": [player.name], "Pro Team": [player.proTeam], "FPTS": player.points})
            positionPriority = 0

            for position in player.eligibleSlots:
                positionPriority += 1
                if positionPriority == 1:
                    df_row["Position"] = [position]
                elif position in eligiblePositions:
                    if positionPriority == 2:
                        df_row["Position2"] = [position]
                    else:
                        df_row["Position3"] = [position]
                else:
                    break

            for key, value in player.points_breakdown.items():
                df_row[key] = [value]

            df = pd.concat([df, df_row])

        for player in boxScore.away_lineup:
            df_row = pd.DataFrame({"Year": [year], "Week": [week], "Team Name": [boxScore.away_team.team_name], "Player Name": [player.name], "Pro Team": [player.proTeam], "FPTS": player.points})
            positionPriority = 0

            for position in player.eligibleSlots:
                positionPriority += 1
                if positionPriority == 1:
                    df_row["Position"] = [position]
                elif position in eligiblePositions:
                    if positionPriority == 2:
                        df_row["Position2"] = [position]
                    else:
                        df_row["Position3"] = [position]
                else:
                    break

            for key, value in player.points_breakdown.items():
                df_row[key] = [value]

            df = pd.concat([df, df_row])

#print(df)

df["FPTS"] = pd.to_numeric(df["FPTS"])
df["FTA"] = pd.to_numeric(df["FTA"])
df["PTS"] = pd.to_numeric(df["PTS"])
df["3PM"] = pd.to_numeric(df["3PM"])
df["BLK"] = pd.to_numeric(df["BLK"])
df["STL"] = pd.to_numeric(df["STL"])
df["AST"] = pd.to_numeric(df["AST"])
df["REB"] = pd.to_numeric(df["REB"])
df["TO"] = pd.to_numeric(df["TO"])
df["FGM"] = pd.to_numeric(df["FGM"])
df["FGA"] = pd.to_numeric(df["FGA"])
df["FTM"] = pd.to_numeric(df["FTM"])

#Set up connection to Google Sheet
#Follow instructions in following article to generate the json keyfile name
#https://mljar.com/blog/authenticate-python-google-sheets-service-account-json-credentials/
scope = ['https://spreadsheets.google.com/feeds',
         'https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_name(
    'basketball-brawl-fant-48835f8bd41a.json', scope) #enter keyfile_name in quotes
gc = gspread.authorize(credentials)
spreadsheet_key = '1uuf5ZyqK4V8G6nNKaSKpWVYqhsk3zdW2wP1e7PTgPkY' #enter spreadsheet id in quotes
wks_name = 'basketballBrawl' #enter worksheet name in quotes


#Fill NaN values with blanks
df = df.fillna('')


#Put the dataframe values in a list
df_values = [df.columns.tolist()] + df.values.tolist() #with column names
#df_values = df.values.tolist() #without column names



#Open the Google Sheet
gs = gc.open_by_key(spreadsheet_key)


#Remove data from this year to overwrite
gs.values_clear("Sheet2!A1:U3000")  #Update sheet name and cells


#Append data to the Google Sheet
gs.values_append('Sheet2', {'valueInputOption': 'RAW'}, {'values': df_values}) #Update sheet name