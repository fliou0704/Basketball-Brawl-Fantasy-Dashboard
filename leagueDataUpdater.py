from espn_api.basketball import League
import pandas as pd
from datetime import datetime
import numpy as np

league_id = 609694684
swid = "{462737C8-F92F-4033-8AD6-1D877AC43C1D}"
espn_s2 = "AEAgnCeltBfv4nKLUgjlax5tsKzVho%2B6cA1L370VKGvF%2B8hlSX4dpV6Gv7kWYNR5t3zCcNNNwmdXlDPD3HMHLCK%2B6EjbZSYRcIKDl32HUTlKJYweuLKQkzjVDaj89PrtCQ6Cv5zujpbZo7SZ50hqICxorzGB3w01Tds62R78b4wQctPA8rL%2ByshLkXQXs9BM8f9ULC5JywoL3i%2B98bHo%2F9JzYyqmCdUvC1ugiM%2F5%2BY63l49PvhdpoEkbn340BC6gShqus0164TuLh28VviKz6JwKssbPorWtoA%2Fx5RhSs%2FLarA%3D%3D"

current_year = datetime.now().year
current_year = current_year + 1
leagueYear = current_year
try:
    league = League(league_id=league_id, year=leagueYear, espn_s2=espn_s2, swid=swid)
except Exception as e:
    year = leagueYear - 1
    league = League(league_id=league_id, year=year, espn_s2=espn_s2, swid=swid)
    leagueYear = year

data = pd.read_csv("data/basketballBrawlLeagueData.csv")

maxyear = data["Year"].max()
maxweek = data[data["Year"] == maxyear]["Week"].max()

yearsToUpdate = []

if (maxyear != leagueYear):
    league = League(league_id=league_id, year=maxyear, espn_s2=espn_s2, swid=swid)
    if (maxweek != len(league.settings.matchup_periods)):
        yearsToUpdate.append(maxyear)
    year = maxyear
    while(year != leagueYear):
        year += 1
        yearsToUpdate.append(year)
else:
    league = League(league_id=league_id, year=maxyear, espn_s2=espn_s2, swid=swid)
    if (maxweek != league.currentMatchupPeriod - 1):
        if (league.currentMatchupPeriod == len(league.settings.matchup_periods)):
            if (league.scoreboard(league.currentMatchupPeriod)[0].winner != "UNDECIDED"):
                if (maxweek != league.currentMatchupPeriod):
                    yearsToUpdate.append(maxyear)
        else:    
            yearsToUpdate.append(maxyear)

#print(yearsToUpdate)

all_data = data[~data["Year"].isin(yearsToUpdate)]

for year in yearsToUpdate:

    if year == 2023:
        espn_s2 = 'AEB%2BZ33nD3CVjTy1%2BY7Y6lYP5KSTfdAI6lUjIpSJ8WHLUyjlIMjYKiJlolvuDTyLPBjdhVHIE5UlyyOh6M%2BWtfB1WA5v2CtQhc1CVjmoF%2B%2BgYmTNE%2FDJgSUC0ws0N9S%2Bermktd4xrMRGnr6C%2FpE2hqqe%2BSjMMAVw941%2F%2BAqJw5qqPpT4LfO4BQuSGepw20APuVapbRM3uzCzqadS91HCK0%2BTQhEpm1lpVCGlqCx%2F6rb0UwYNqjJeLkbuXXbrkqK9mPrg5QAqGRI914K2U%2Bah2yD08dXZ8xfYB7K0ilPeqJPKJA%3D%3D'
    else:
        espn_s2 = "AEAgnCeltBfv4nKLUgjlax5tsKzVho%2B6cA1L370VKGvF%2B8hlSX4dpV6Gv7kWYNR5t3zCcNNNwmdXlDPD3HMHLCK%2B6EjbZSYRcIKDl32HUTlKJYweuLKQkzjVDaj89PrtCQ6Cv5zujpbZo7SZ50hqICxorzGB3w01Tds62R78b4wQctPA8rL%2ByshLkXQXs9BM8f9ULC5JywoL3i%2B98bHo%2F9JzYyqmCdUvC1ugiM%2F5%2BY63l49PvhdpoEkbn340BC6gShqus0164TuLh28VviKz6JwKssbPorWtoA%2Fx5RhSs%2FLarA%3D%3D"

    league = League(league_id=league_id, year=year, espn_s2=espn_s2, swid=swid)
    regularWeeks = league.settings.reg_season_count
    totalWeeks = len(league.settings.matchup_periods)
    startingWeek = 1
    if not (data[data["Year"] == year].empty):
        startingWeek = data[data["Year"] == year]["Week"].max()
    #print(year)
    #print(leagueYear)
    endingWeek = league.currentMatchupPeriod
    if (endingWeek == totalWeeks):
        if (league.scoreboard(endingWeek)[0].winner != "UNDECIDED"):
            endingWeek = endingWeek + 1

    df = pd.DataFrame(columns=["Year", "Week", "Type", "Team Name", "Team Abbreviation", "Team ID", "Team Owner", "Home/Away", "Points For", "Points Against", "Win", "Loss", "Opponent Team Name", "Opponent Team ID", "Opponent Owner"])
    if startingWeek != 1:
        df = data[data["Year"] == year]
    
    #print(str(year) + ": Week " + str(startingWeek) + " - Week " + str(endingWeek - 1))

    for week in range(startingWeek, endingWeek):
        #print("Week " + str(week))
        # df_row = [year, week, team name, team abbreviation, team id, team owner, home/away, points for, points against, win, loss, opponenet team name, opponent team id, opponent team owner]
        type = "Regular"
        eliminated = []
        firstRoundByes = []
        lastRankDict = dict()
        if week > regularWeeks:
            type = "Playoffs"
        if week == regularWeeks + 1:
            lastWeek = df.loc[(df["Year"] == year) & (df["Week"] == week - 1)]
            lastRankDict = dict(zip(lastWeek['Team ID'], lastWeek['Rank']))
            eliminated = [team_id for team_id, rank in lastRankDict.items() if rank > 6]
            eliminated = eliminated[:4]
        elif week == regularWeeks + 2:
            lastWeek = data.loc[(data["Year"] == year) & (data["Week"] == week - 1)]
            if lastWeek.empty:
                lastWeek = df.loc[(df["Year"] == year) & (df["Week"] == week - 1)]
            lastRankDict = dict(zip(lastWeek['Team ID'], lastWeek['Rank']))
            eliminated = [team_id for team_id, rank in lastRankDict.items() if rank > 4]
            eliminated = eliminated[:6]
        elif week == regularWeeks + 3:
            lastWeek = data.loc[(data["Year"] == year) & (data["Week"] == week - 1)]
            if lastWeek.empty:
                lastWeek = df.loc[(df["Year"] == year) & (df["Week"] == week - 1)]
            lastRankDict = dict(zip(lastWeek['Team ID'], lastWeek['Rank']))
            eliminated = [team_id for team_id, rank in lastRankDict.items() if rank > 2]
            eliminated = eliminated[:8]
        for matchup in league.scoreboard(week):
            if week == regularWeeks + 1:
                homeTeam = matchup.home_team
                awayTeam = matchup.away_team
                if homeTeam == 0:
                    firstRoundByes.append(awayTeam)
                    continue
                if awayTeam == 0:
                    firstRoundByes.append(homeTeam)
                    continue

            homeTeam = matchup.home_team
            awayTeam = matchup.away_team

            if homeTeam.team_id in eliminated:
                type = "Consolation"
            if awayTeam.team_id in eliminated:
                type = "Consolation"

            home_df_row = pd.DataFrame({"Year": [year], "Week": [week], "Type": [type], "Team Name": [homeTeam.team_name], "Team Abbreviation": [homeTeam.team_abbrev],"Team ID": [homeTeam.team_id], "Team Owner": [homeTeam.owners[0]['firstName']]})
            away_df_row = pd.DataFrame({"Year": [year], "Week": [week], "Type": [type], "Team Name": [awayTeam.team_name], "Team Abbreviation": [awayTeam.team_abbrev],"Team ID": [awayTeam.team_id], "Team Owner": [awayTeam.owners[0]['firstName']]})

            homePlace = "HOME"
            awayPlace = "AWAY"

            homeResult = ""
            awayResult = ""
            if matchup.winner == homePlace:
                homeResult = "W"
                awayResult = "L"
                home_df_row["Win"] = [1]
                away_df_row["Win"] = [0]
                home_df_row["Loss"] = [0]
                away_df_row["Loss"] = [1]
            else:
                homeResult = "L"
                awayResult = "W"
                home_df_row["Win"] = [0]
                away_df_row["Win"] = [1]
                home_df_row["Loss"] = [1]
                away_df_row["Loss"] = [0]

            home_df_row["Home/Away"] = ["Home"]
            away_df_row["Home/Away"] = ["Away"]

            home_df_row["Points For"] = [matchup.home_final_score]
            away_df_row["Points For"] = [matchup.away_final_score]

            home_df_row["Points Against"] = [matchup.away_final_score]
            away_df_row["Points Against"] = [matchup.home_final_score]

            home_df_row["Opponent Team Name"] = [awayTeam.team_name]
            away_df_row["Opponent Team Name"] = [homeTeam.team_name]

            home_df_row["Opponent Team ID"] = [awayTeam.team_id]
            away_df_row["Opponent Team ID"] = [homeTeam.team_id]

            home_df_row["Opponent Owner"] = [awayTeam.owners[0]['firstName']]
            away_df_row["Opponent Owner"] = [homeTeam.owners[0]['firstName']]
            if df.empty:
                df = home_df_row
                df = pd.concat([df, away_df_row])
            else:
                df = pd.concat([df, home_df_row])
                df = pd.concat([df, away_df_row])

        if len(firstRoundByes) != 0:
            for team in firstRoundByes:
                type = "Bye"
                df_row = pd.DataFrame({"Year": [year], "Week": [week], "Type": [type], "Team Name": [team.team_name], "Team Abbreviation": [team.team_abbrev],"Team ID": [team.team_id], "Team Owner": [team.owners[0]['firstName']]})
                place = ""
                result = ""
                df_row["Win"] = [0]

                df_row["Loss"] = [0]

                df_row["Home/Away"] = [""]

                df_row["Points For"] = [0]

                df_row["Points Against"] = [0]

                df_row["Opponent Team Name"] = [""]

                df_row["Opponent Team ID"] = [""]

                df_row["Opponent Owner"] = [""]
                if df.empty:
                    df = df_row
                else:
                    df = pd.concat([df, df_row])

        df["Points For"] = pd.to_numeric(df["Points For"])
        df["Points Against"] = pd.to_numeric(df["Points Against"])
        df["Win"] = pd.to_numeric(df["Win"])
        df["Loss"] = pd.to_numeric(df["Loss"])

        df["Cumulative Points For"] = df["Points For"].groupby(df["Team Name"]).cumsum()
        df["Cumulative Points Against"] = df["Points Against"].groupby(df["Team Name"]).cumsum()
        df["Cumulative Wins"] = df["Win"].groupby(df["Team Name"]).cumsum()
        df["Cumulative Losses"] = df["Loss"].groupby(df["Team Name"]).cumsum()

        df['Weekly Rank'] = df.groupby('Week')['Points For'].rank(ascending=False, method='min').astype(int)
        df = df.sort_values(by=['Week', 'Cumulative Wins', 'Cumulative Points For'], ascending=[True, False, False])
        df['Rank'] = df.groupby('Week').cumcount() + 1

        if week > regularWeeks:
            for id in eliminated:
                df.loc[(df["Week"] == week) & (df["Team ID"] == id), "Rank"] = lastRankDict[id]

            losers = df[
                    (df["Type"] == "Playoffs") &
                    (df["Week"] == week) &
                    (df["Loss"] == 1)
                ]["Team ID"].tolist()
            
            winners = df[
                    (df["Type"] == "Playoffs") &
                    (df["Week"] == week) &
                    (df["Win"] == 1)
                ]["Team ID"].tolist()
                
            if week == regularWeeks + 1:
                if lastRankDict[losers[0]] > lastRankDict[losers[1]]:
                    df.loc[(df["Week"] == week) & (df["Team ID"] == losers[0]), "Rank"] = 6
                    df.loc[(df["Week"] == week) & (df["Team ID"] == losers[1]), "Rank"] = 5
                else:
                    df.loc[(df["Week"] == week) & (df["Team ID"] == losers[0]), "Rank"] = 5
                    df.loc[(df["Week"] == week) & (df["Team ID"] == losers[1]), "Rank"] = 6

    
                if lastRankDict[winners[0]] > lastRankDict[winners[1]]:
                    df.loc[(df["Week"] == week) & (df["Team ID"] == winners[0]), "Rank"] = 4
                    df.loc[(df["Week"] == week) & (df["Team ID"] == winners[1]), "Rank"] = 3
                else:
                    df.loc[(df["Week"] == week) & (df["Team ID"] == winners[0]), "Rank"] = 3
                    df.loc[(df["Week"] == week) & (df["Team ID"] == winners[1]), "Rank"] = 4


                if lastRankDict[firstRoundByes[0].team_id] > lastRankDict[firstRoundByes[1].team_id]:
                    df.loc[(df["Week"] == week) & (df["Team ID"] == firstRoundByes[0].team_id), "Rank"] = 2
                    df.loc[(df["Week"] == week) & (df["Team ID"] == firstRoundByes[1].team_id), "Rank"] = 1
                else:
                    df.loc[(df["Week"] == week) & (df["Team ID"] == firstRoundByes[0].team_id), "Rank"] = 1
                    df.loc[(df["Week"] == week) & (df["Team ID"] == firstRoundByes[1].team_id), "Rank"] = 2

            elif week == regularWeeks + 2:
                if lastRankDict[losers[0]] > lastRankDict[losers[1]]:
                    df.loc[(df["Week"] == week) & (df["Team ID"] == losers[0]), "Rank"] = 4
                    df.loc[(df["Week"] == week) & (df["Team ID"] == losers[1]), "Rank"] = 3
                else:
                    df.loc[(df["Week"] == week) & (df["Team ID"] == losers[0]), "Rank"] = 3
                    df.loc[(df["Week"] == week) & (df["Team ID"] == losers[1]), "Rank"] = 4

    
                if lastRankDict[winners[0]] > lastRankDict[winners[1]]:
                    df.loc[(df["Week"] == week) & (df["Team ID"] == winners[0]), "Rank"] = 2
                    df.loc[(df["Week"] == week) & (df["Team ID"] == winners[1]), "Rank"] = 1
                else:
                    df.loc[(df["Week"] == week) & (df["Team ID"] == winners[0]), "Rank"] = 1
                    df.loc[(df["Week"] == week) & (df["Team ID"] == winners[1]), "Rank"] = 2
            
            else:
                df.loc[(df["Week"] == week) & (df["Team ID"] == losers[0]), "Rank"] = 2
                df.loc[(df["Week"] == week) & (df["Team ID"] == winners[0]), "Rank"] = 1

    df = df.sort_values(by='Week').reset_index(drop=True)

    # Append to master dataframe
    if all_data.empty:
        #print('HI')
        all_data = df
    else:
        all_data = pd.concat([all_data, df], ignore_index=True)
    #print(df)

all_data.to_csv('data/TESTINGbasketballBrawlLeagueData.csv', index=False)