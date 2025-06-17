from espn_api.basketball import League
import pandas as pd
import numpy as np

#import sys
#print(sys.path)

league_id = 609694684
swid = "{462737C8-F92F-4033-8AD6-1D877AC43C1D}"
espn_s2 = "AEAgnCeltBfv4nKLUgjlax5tsKzVho%2B6cA1L370VKGvF%2B8hlSX4dpV6Gv7kWYNR5t3zCcNNNwmdXlDPD3HMHLCK%2B6EjbZSYRcIKDl32HUTlKJYweuLKQkzjVDaj89PrtCQ6Cv5zujpbZo7SZ50hqICxorzGB3w01Tds62R78b4wQctPA8rL%2ByshLkXQXs9BM8f9ULC5JywoL3i%2B98bHo%2F9JzYyqmCdUvC1ugiM%2F5%2BY63l49PvhdpoEkbn340BC6gShqus0164TuLh28VviKz6JwKssbPorWtoA%2Fx5RhSs%2FLarA%3D%3D"

years = [2023, 2024, 2025]

all_data = pd.DataFrame(columns=["Year", "Week", "Type", "Team Name", "Team ID", "Team Owner", "Home/Away", "Points For", "Points Against", "Win", "Loss", "Opponent Team Name"])

for year in years:

    if year == 2023:
        espn_s2 = 'AEB%2BZ33nD3CVjTy1%2BY7Y6lYP5KSTfdAI6lUjIpSJ8WHLUyjlIMjYKiJlolvuDTyLPBjdhVHIE5UlyyOh6M%2BWtfB1WA5v2CtQhc1CVjmoF%2B%2BgYmTNE%2FDJgSUC0ws0N9S%2Bermktd4xrMRGnr6C%2FpE2hqqe%2BSjMMAVw941%2F%2BAqJw5qqPpT4LfO4BQuSGepw20APuVapbRM3uzCzqadS91HCK0%2BTQhEpm1lpVCGlqCx%2F6rb0UwYNqjJeLkbuXXbrkqK9mPrg5QAqGRI914K2U%2Bah2yD08dXZ8xfYB7K0ilPeqJPKJA%3D%3D'
    else:
        espn_s2 = "AEAgnCeltBfv4nKLUgjlax5tsKzVho%2B6cA1L370VKGvF%2B8hlSX4dpV6Gv7kWYNR5t3zCcNNNwmdXlDPD3HMHLCK%2B6EjbZSYRcIKDl32HUTlKJYweuLKQkzjVDaj89PrtCQ6Cv5zujpbZo7SZ50hqICxorzGB3w01Tds62R78b4wQctPA8rL%2ByshLkXQXs9BM8f9ULC5JywoL3i%2B98bHo%2F9JzYyqmCdUvC1ugiM%2F5%2BY63l49PvhdpoEkbn340BC6gShqus0164TuLh28VviKz6JwKssbPorWtoA%2Fx5RhSs%2FLarA%3D%3D"

    league = League(league_id=league_id, year=year, espn_s2=espn_s2, swid=swid)

    df = pd.DataFrame(columns=["Year", "Week", "Type", "Team Name", "Home/Away", "Points For", "Points Against", "Win", "Loss", "Opponent Team Name"])

    for team in league.teams:
        # df_row = [year, week, team name, team id, team owner, home/away, points for, points against, win, loss, opponenet team name, opponent team id, opponent team owner]
        week = 0
        scheduleLen = len(team.schedule)
        for matchup in team.schedule:
            week += 1
            if week > scheduleLen - 3:
                type = 'Playoffs'
            else:
                type = 'Regular'
            df_row = pd.DataFrame({"Year": [year], "Week": [week], "Type": [type], "Team Name": [team.team_name], "Team ID": [team.team_id], "Owner": [team.owners[0]['firstName']]})
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
                df_row["Opponent Team ID"] = [matchup.away_team.team_id]
                df_row["Opponent Owner"] = [matchup.away_team.owners[0]['firstName']]
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
                df_row["Opponent Team ID"] = [matchup.home_team.team_id]
                df_row["Opponent Owner"] = [matchup.home_team.owners[0]['firstName']]
                #print(matchup.away_team.team_name, matchup.away_final_score, matchup.home_team.team_name, matchup.home_final_score, place, result)
            if df.empty:
                df = df_row
            else:
                df = pd.concat([df, df_row])
        #print("\n")

    df["Points For"] = pd.to_numeric(df["Points For"])
    df["Points Against"] = pd.to_numeric(df["Points Against"])
    df["Win"] = pd.to_numeric(df["Win"])
    df["Loss"] = pd.to_numeric(df["Loss"])

    ### Fixing first round bye playoff schedules
    teamGP = df.groupby("Team ID").size().reset_index(name='Count')
    teams = teamGP["Team ID"]
    totalWeeks = teamGP["Count"].mode().iloc[0]
    finalRegularWeek = totalWeeks - 3
    firstRoundByes = []
    teamCountDict = dict(zip(teamGP['Team ID'], teamGP['Count']))
    while(len(firstRoundByes) < 2):
        for id in teamGP["Team ID"]:
            if teamCountDict.get(id) != totalWeeks:
                firstRoundByes.append(id)

    for team in firstRoundByes:
        #Fix matchup type for last week of regular season
        row_mask = (df['Team ID'] == team) & (df['Week'] == finalRegularWeek)
        df.loc[row_mask, 'Type'] = "Regular"
        weeksAdjusted = 0
        weekAdjusting = totalWeeks - 1
        while(weeksAdjusted < 2):
            row_mask = (df['Team ID'] == team) & (df['Week'] == weekAdjusting)
            df.loc[row_mask, 'Week'] = df.loc[row_mask]['Week'] + 1
            weekAdjusting -= 1
            weeksAdjusted += 1


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

    #df['Weekly Rank'] = df.groupby('Week')['Points For'].rank(ascending=False, method='min').astype(int)

    for team in firstRoundByes:
        bye_row_mask = row_mask_final = (df['Team ID'] == team) & (df['Week'] == finalRegularWeek)
        bye_row = {
            'Year': year,
            'Week': finalRegularWeek + 1,
            'Type': 'Bye',
            'Team Name': df.loc[bye_row_mask, "Team Name"].iloc[0],
            'Team ID': team,
            'Owner': df.loc[bye_row_mask, "Owner"].iloc[0],
            'Home/Away': 'Bye',
            'Points For': 0,
            'Points Against': 0,
            'Win': 0,
            'Loss': 0,
            'Opponent Team Name': None,
            'Opponent Team ID': None,
            'Opponent Owner': None,
            'Cumulative Points For': df.loc[bye_row_mask, "Cumulative Points For"].iloc[0],  # carry over from prior week
            'Cumulative Points Against': df.loc[bye_row_mask, "Cumulative Points Against"].iloc[0],
            'Cumulative Wins': df.loc[bye_row_mask, "Cumulative Wins"].iloc[0],
            'Cumulative Losses': df.loc[bye_row_mask, "Cumulative Losses"].iloc[0],
            'Weekly Rank': np.nan,
            'Rank': np.nan
        }
        df = pd.concat([df, pd.DataFrame([bye_row])], ignore_index=True)

    df['Weekly Rank'] = df.groupby('Week')['Points For'].rank(ascending=False, method='min').astype(int)

    # Sort data for rank regular season rank assignments
    df = df.sort_values(by=['Week', 'Cumulative Wins', 'Cumulative Points For'], ascending=[True, False, False])
    df['Rank'] = df.groupby('Week').cumcount() + 1

    ### Fixing playoff rankings
    finalRegularWeekdf = df[df["Week"] == finalRegularWeek]
    finalRegularRankDict = dict(zip(finalRegularWeekdf['Team ID'], finalRegularWeekdf['Rank']))
    eliminated = []
    while(len(eliminated) < 4):
        for id in finalRegularWeekdf["Team ID"]:
            if finalRegularRankDict.get(id) > 6:
                eliminated.append(id)

    ## Fixing rankings throughout playoffs and adding the 'consolation' matchup type
    ## Possibly add week 0 to reflect rankings from the previous season.
    weekAdjusting = totalWeeks - 2
    while(weekAdjusting <= totalWeeks):
        losers = []
        for team in teams:
            if team in eliminated:
                # row mask to get eliminated team's rank from previous week
                row_mask_final = (df['Team ID'] == team) & (df['Week'] == weekAdjusting - 1)
                # row mask to update eliminated team's rank for this week
                row_mask_adjust = (df['Team ID'] == team) & (df['Week'] == weekAdjusting)
                df.loc[row_mask_adjust, 'Rank'] = df.loc[row_mask_final, 'Rank'].iloc[0]
                # Since this team is already eliminated from the playoffs, their match is a consolation match
                df.loc[row_mask_adjust, 'Type'] = "Consolation"
            else:
                row_mask_final = (df['Team ID'] == team) & (df['Week'] == finalRegularWeek)
                row_mask_adjust = (df['Team ID'] == team) & (df['Week'] == weekAdjusting)
                if row_mask_adjust.any():
                    if df.loc[row_mask_adjust, "Cumulative Losses"].iloc[0] > df.loc[row_mask_final, "Cumulative Losses"].iloc[0]:
                        # add teams that lost to a losers array to adjust rankings accordingly
                        losers.append(team)
        winners = [team for team in teams if team not in eliminated and team not in losers and team not in firstRoundByes]
        if weekAdjusting != totalWeeks:
            row_mask_loser1 = (df['Team ID'] == losers[0]) & (df['Week'] == finalRegularWeek)
            row_mask_loser1_adjust = (df['Team ID'] == losers[0]) & (df['Week'] == weekAdjusting)
            row_mask_loser2 = (df['Team ID'] == losers[1]) & (df['Week'] == finalRegularWeek)
            row_mask_loser2_adjust = (df['Team ID'] == losers[1]) & (df['Week'] == weekAdjusting)
            row_mask_winner1 = (df['Team ID'] == winners[0]) & (df['Week'] == finalRegularWeek)
            row_mask_winner1_adjust = (df['Team ID'] == winners[0]) & (df['Week'] == weekAdjusting)
            row_mask_winner2 = (df['Team ID'] == winners[1]) & (df['Week'] == finalRegularWeek)
            row_mask_winner2_adjust = (df['Team ID'] == winners[1]) & (df['Week'] == weekAdjusting)
            # if it is the first week of the playoffs
            if weekAdjusting == totalWeeks - 2:
                row_mask_frb1 = (df['Team ID'] == firstRoundByes[0]) & (df['Week'] == finalRegularWeek)
                row_mask_frb1_adjust = (df['Team ID'] == firstRoundByes[0]) & (df['Week'] == weekAdjusting)
                row_mask_frb2 = (df['Team ID'] == firstRoundByes[1]) & (df['Week'] == finalRegularWeek)
                row_mask_frb2_adjust = (df['Team ID'] == firstRoundByes[1]) & (df['Week'] == weekAdjusting)
                # update loser rankings
                if df.loc[row_mask_loser1, "Rank"].iloc[0] > df.loc[row_mask_loser2, "Rank"].iloc[0]:
                    df.loc[row_mask_loser1_adjust, "Rank"] = 6
                    df.loc[row_mask_loser2_adjust, "Rank"] = 5
                else:
                    df.loc[row_mask_loser1_adjust, "Rank"] = 5
                    df.loc[row_mask_loser2_adjust, "Rank"] = 6
                # update winner rankings
                if df.loc[row_mask_winner1, "Rank"].iloc[0] > df.loc[row_mask_winner2, "Rank"].iloc[0]:
                    df.loc[row_mask_winner1_adjust, "Rank"] = 4
                    df.loc[row_mask_winner2_adjust, "Rank"] = 3
                else:
                    df.loc[row_mask_winner1_adjust, "Rank"] = 3
                    df.loc[row_mask_winner2_adjust, "Rank"] = 4
                # update first round bye rankings
                if df.loc[row_mask_frb1, "Rank"].iloc[0] > df.loc[row_mask_frb2, "Rank"].iloc[0]:
                    df.loc[row_mask_frb1_adjust, "Rank"] = 2
                    df.loc[row_mask_frb2_adjust, "Rank"] = 1
                else:
                    df.loc[row_mask_frb1_adjust, "Rank"] = 1
                    df.loc[row_mask_frb2_adjust, "Rank"] = 2
                firstRoundByes = []
            # if it is the second week of the playoffs
            else:
                # update loser rankings
                if df.loc[row_mask_loser1, "Rank"].iloc[0] > df.loc[row_mask_loser2, "Rank"].iloc[0]:
                    df.loc[row_mask_loser1_adjust, "Rank"] = 4
                    df.loc[row_mask_loser2_adjust, "Rank"] = 3
                else:
                    df.loc[row_mask_loser1_adjust, "Rank"] = 3
                    df.loc[row_mask_loser2_adjust, "Rank"] = 4
                # update winner rankings
                if df.loc[row_mask_winner1, "Rank"].iloc[0] > df.loc[row_mask_winner2, "Rank"].iloc[0]:
                    df.loc[row_mask_winner1_adjust, "Rank"] = 2
                    df.loc[row_mask_winner2_adjust, "Rank"] = 1
                else:
                    df.loc[row_mask_winner1_adjust, "Rank"] = 1
                    df.loc[row_mask_winner2_adjust, "Rank"] = 2
            for loser in losers:
                eliminated.append(loser)
            losers = []
        # post-championship adjustments
        else:
            row_mask_runnerUp = (df['Team ID'] == losers[0]) & (df['Week'] == weekAdjusting)
            eliminated.append(losers[0])
            df.loc[row_mask_runnerUp, "Rank"] = 2

            for team in teams:
                if team not in eliminated:
                    row_mask_champion = (df['Team ID'] == team) & (df['Week'] == weekAdjusting)
                    df.loc[row_mask_champion, "Rank"] = 1
        weekAdjusting += 1

    df = df.sort_values(by='Week').reset_index(drop=True)

    # Append to master dataframe
    if all_data.empty:
        all_data = df
    else:
        all_data = pd.concat([all_data, df], ignore_index=True)

all_data.to_csv('basketballBrawlLeagueData.csv', index=False)

#print(df)