from espn_api.basketball import League
import pandas as pd

#import sys
#print(sys.path)

league_id = 609694684
swid = "{462737C8-F92F-4033-8AD6-1D877AC43C1D}"
espn_s2 = "AEAgnCeltBfv4nKLUgjlax5tsKzVho%2B6cA1L370VKGvF%2B8hlSX4dpV6Gv7kWYNR5t3zCcNNNwmdXlDPD3HMHLCK%2B6EjbZSYRcIKDl32HUTlKJYweuLKQkzjVDaj89PrtCQ6Cv5zujpbZo7SZ50hqICxorzGB3w01Tds62R78b4wQctPA8rL%2ByshLkXQXs9BM8f9ULC5JywoL3i%2B98bHo%2F9JzYyqmCdUvC1ugiM%2F5%2BY63l49PvhdpoEkbn340BC6gShqus0164TuLh28VviKz6JwKssbPorWtoA%2Fx5RhSs%2FLarA%3D%3D"

years = [2023, 2024, 2025]

all_data = pd.DataFrame(columns=["Year", "Week", "Type", "Team Name", "Home/Away", "Points For", "Points Against", "Win", "Loss", "Opponent Team Name"])

for year in years:

    if year == 2023:
        espn_s2 = 'AEB%2BZ33nD3CVjTy1%2BY7Y6lYP5KSTfdAI6lUjIpSJ8WHLUyjlIMjYKiJlolvuDTyLPBjdhVHIE5UlyyOh6M%2BWtfB1WA5v2CtQhc1CVjmoF%2B%2BgYmTNE%2FDJgSUC0ws0N9S%2Bermktd4xrMRGnr6C%2FpE2hqqe%2BSjMMAVw941%2F%2BAqJw5qqPpT4LfO4BQuSGepw20APuVapbRM3uzCzqadS91HCK0%2BTQhEpm1lpVCGlqCx%2F6rb0UwYNqjJeLkbuXXbrkqK9mPrg5QAqGRI914K2U%2Bah2yD08dXZ8xfYB7K0ilPeqJPKJA%3D%3D'
    else:
        espn_s2 = "AEAgnCeltBfv4nKLUgjlax5tsKzVho%2B6cA1L370VKGvF%2B8hlSX4dpV6Gv7kWYNR5t3zCcNNNwmdXlDPD3HMHLCK%2B6EjbZSYRcIKDl32HUTlKJYweuLKQkzjVDaj89PrtCQ6Cv5zujpbZo7SZ50hqICxorzGB3w01Tds62R78b4wQctPA8rL%2ByshLkXQXs9BM8f9ULC5JywoL3i%2B98bHo%2F9JzYyqmCdUvC1ugiM%2F5%2BY63l49PvhdpoEkbn340BC6gShqus0164TuLh28VviKz6JwKssbPorWtoA%2Fx5RhSs%2FLarA%3D%3D"

    league = League(league_id=league_id, year=year, espn_s2=espn_s2, swid=swid)

    df = pd.DataFrame(columns=["Year", "Week", "Type", "Team Name", "Home/Away", "Points For", "Points Against", "Win", "Loss", "Opponent Team Name"])

    for team in league.teams:
        # df_row = [year, week, team_name, home/away, points for, points against, win, loss, opponenet team_name]
        week = 0
        firstRoundBye = False
        if len(team.schedule) < 23:
            firstRoundBye = True
        for matchup in team.schedule:
            week += 1
            if week == 21 and firstRoundBye:
                week += 1
            type = 'Regular'
            if week > 20:
                type = 'Playoffs'
            df_row = pd.DataFrame({"Year": [year], "Week": [week], "Type": [type], "Team Name": [team.team_name]})
            place = ""
            result = ""
            #print(matchup.winner)
            if matchup.home_team.team_name == team.team_name:
                place = "HOME"
                df_row["Home/Away"] = ["Home"]
                df_row["Points For"] = [matchup.home_final_score]
                df_row["Points Against"] = [matchup.away_final_score]
                if matchup.winner == place:
                    result = "W"
                    df_row["Win"] = [1]
                    df_row["Loss"] = [0]
                else:
                    result = "L"
                    df_row["Win"] = [0]
                    df_row["Loss"] = [1]
                df_row["Opponent Team Name"] = [matchup.away_team.team_name]
                #print(matchup.home_team.team_name, matchup.home_final_score, matchup.away_team.team_name, matchup.away_final_score, place, result)
            else:
                place = "AWAY"
                df_row["Home/Away"] = ["Away"]
                df_row["Points For"] = [matchup.away_final_score]
                df_row["Points Against"] = [matchup.home_final_score]
                if matchup.winner == place:
                    result = "W"
                    df_row["Win"] = [1]
                    df_row["Loss"] = [0]
                else:
                    result = "L"
                    df_row["Win"] = [0]
                    df_row["Loss"] = [1]
                df_row["Opponent Team Name"] = [matchup.home_team.team_name]
                #print(matchup.away_team.team_name, matchup.away_final_score, matchup.home_team.team_name, matchup.home_final_score, place, result)
            df = pd.concat([df, df_row])
        #print("\n")

    df["Points For"] = pd.to_numeric(df["Points For"])
    df["Points Against"] = pd.to_numeric(df["Points Against"])
    df["Win"] = pd.to_numeric(df["Win"])
    df["Loss"] = pd.to_numeric(df["Loss"])

    df["Cumulative Points For"] = df["Points For"].groupby(df["Team Name"]).cumsum()
    df["Cumulative Points Against"] = df["Points Against"].groupby(df["Team Name"]).cumsum()
    df["Cumulative Wins"] = df["Win"].groupby(df["Team Name"]).cumsum()
    df["Cumulative Losses"] = df["Loss"].groupby(df["Team Name"]).cumsum()

    df = df.sort_values("Week")
    #print(df)

    #Add a rank column based on league logic
    #df['Rank'] = (df.sort_values(['Cumulative Wins','Cumulative Points For'])
    #                      .groupby(['Week']).cumcount(ascending=False)+1)
    #df['Rank'] = df.groupby('Week')['Cumulative Wins','Cumulative Points For'].rank(ascending=False, method='min').astype(int)

    df['Weekly Rank'] = df.groupby('Week')['Points For'].rank(ascending=False, method='min').astype(int)

    df = df.sort_values(by=['Week', 'Cumulative Wins', 'Cumulative Points For'], ascending=[True, False, False])

    # Step 3: Assign rank based on sorted order within each week
    df['Rank'] = df.groupby('Week').cumcount() + 1

    ### Trying to fix end of season standings
    latest_week = df['Week'].max()
    for team in league.teams:
        df.loc[(df['Team Name'] == team.team_name) & (df['Week'] == latest_week), 'Rank'] = team.final_standing

    df = df.sort_values(by='Week').reset_index(drop=True)

    # Append to master dataframe
    all_data = pd.concat([all_data, df], ignore_index=True)

all_data.to_csv('basketballBrawlLeagueData.csv', index=False)

#print(df)