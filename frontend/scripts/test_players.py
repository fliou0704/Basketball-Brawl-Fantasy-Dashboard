import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from generate_players import aggregate_career, build, current_ownership, game_log, latest_eligibility, transaction_history


class PlayerCareerExportTests(unittest.TestCase):
    def test_active_played_rows_only_and_multi_team_order_and_totals(self):
        daily = pd.DataFrame([
            {"Year": 2026, "Date": "2025-11-03", "Team ID": 7, "FPTS": 20, "MIN": 10, "PTS": 10, "REB": 4, "AST": 4, "STL": 4, "BLK": 0, "3PM": 2, "TO": -2, "FGM": 8, "FGA": -16, "FTM": 2, "FTA": -2},
            {"Year": 2026, "Date": "2025-10-20", "Team ID": 2, "FPTS": 30, "MIN": 30, "PTS": 14, "REB": 5, "AST": 6, "STL": 0, "BLK": 4, "3PM": 1, "TO": -4, "FGM": 10, "FGA": -20, "FTM": 3, "FTA": -4},
        ])
        teams={2:{"teamId":2,"teamName":"First","logo":"logos/first.png"},7:{"teamId":7,"teamName":"Second","logo":"logos/second.png"}}
        rows, total=aggregate_career(daily,teams)
        stints=[row for row in rows if row["rowType"]=="stint"]
        season_total=rows[-1]
        self.assertEqual([row["team"]["teamId"] for row in stints],[2,7])
        self.assertEqual(season_total["rowType"],"seasonTotal")
        self.assertEqual(total["starts"],2)
        self.assertEqual(total["FPTS"],sum(row["FPTS"] for row in stints))
        self.assertEqual(total["FGM"],9)
        self.assertEqual(total["AST"],5)
        self.assertEqual(total["TO"],3)
        self.assertEqual(total["fpPerStart"],25)
        self.assertEqual(total["mpg"],20)
        self.assertEqual(total["fppm"],1.25)
        self.assertEqual(season_total["FPTS"],total["FPTS"])
        self.assertNotEqual(total["fppm"],sum(row["fppm"] for row in stints)/len(stints))

    def test_return_to_a_prior_team_remains_a_separate_stint(self):
        base={"Year":2026,"FPTS":10,"MIN":10,"PTS":1,"REB":1,"AST":2,"STL":0,"BLK":0,"3PM":0,"TO":0,"FGM":2,"FGA":-2,"FTM":0,"FTA":0}
        daily=pd.DataFrame([{**base,"Scoring Period":1,"Date":"2025-10-20","Team ID":2},{**base,"Scoring Period":5,"Date":"2025-10-24","Team ID":7},{**base,"Scoring Period":10,"Date":"2025-10-29","Team ID":2},{**base,"Scoring Period":20,"Date":"2025-11-08","Team ID":2}])
        teams={2:{"teamId":2},7:{"teamId":7}}
        rows,_=aggregate_career(daily,teams)
        stints=[row for row in rows if row["rowType"]=="stint"]
        self.assertEqual([row["team"]["teamId"] for row in stints],[2,7,2])
        self.assertEqual(stints[-1]["starts"],2)  # The scoring-period gap does not split Team A.

    def test_latest_fantasy_eligibility_and_current_ownership(self):
        daily=pd.DataFrame([
            {"Year":2025,"Scoring Period":100,"Date":"2025-03-01","Player ID":1,"Position":"SG","Position2":None,"Position3":None},
            {"Year":2026,"Scoring Period":2,"Date":"2025-10-20","Player ID":1,"Position":"SG","Position2":"SF","Position3":None},
        ])
        self.assertEqual(latest_eligibility(daily)[1],["SG","SF"])
        teams={2:{"teamId":2},7:{"teamId":7}}
        activity=pd.DataFrame([
            {"Year":2026,"Date":"2025-10-01","Time":"06:00","Player ID":1,"Team ID":2,"Action":"DRAFTED"},
            {"Year":2026,"Date":"2025-11-01","Time":"06:00","Player ID":1,"Team ID":2,"Action":"TRADED"},
            {"Year":2026,"Date":"2025-11-01","Time":"06:00","Player ID":1,"Team ID":7,"Action":"RECEIVED"},
            {"Year":2026,"Date":"2025-12-01","Time":"06:00","Player ID":2,"Team ID":7,"Action":"DROPPED"},
        ])
        owners=current_ownership(activity,teams)
        self.assertEqual(owners[1]["teamId"],7)
        self.assertNotIn(2,owners)  # Fantasy free agent.

    def test_build_excludes_bench_and_non_played_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); source=root/"data"; output=root/"public"; source.mkdir()
            pd.DataFrame([{"ESPN Player ID":1,"Full Name":"Test Player","Active":False}]).to_csv(source/"playerMetadata.csv",index=False)
            base={"Year":2026,"Scoring Period":1,"Date":"2025-10-20","Team Name":"One","Team ID":1,"Player Name":"Test Player","Player ID":1,"Position":"PG","Position2":None,"Position3":None,"FPTS":10,"MIN":20,"FTA":-2,"PTS":5,"3PM":1,"BLK":0,"STL":0,"AST":2,"REB":2,"TO":-2,"FGM":4,"FGA":-8,"FTM":1}
            pd.DataFrame([{**base,"Player Slot":"PG"},{**base,"Scoring Period":2,"Date":"2025-10-21","Player Slot":"BE"},{**base,"Scoring Period":3,"Date":"2025-10-22","Player Slot":"PG","MIN":0}]).to_csv(source/"playerDailyData.csv",index=False)
            pd.DataFrame([{"Year":2026,"Week":1,"Type":"Regular","Team Name":"One","Team ID":1,"Team Owner":"Owner"}]).to_csv(source/"basketballBrawlLeagueData.csv",index=False)
            pd.DataFrame([{"Year":2026,"Date":"2025-10-01","Time":"06:00","Team Name":"One","Action":"DRAFTED","Team ID":1,"Player ID":1}]).to_csv(source/"activityData.csv",index=False)
            metadata={"seasons":[{"season":2026,"lineupSlots":["PG"]}]}
            config={"team_logo_paths":{"One":"assets/logos/One.png"},"default_logo_path":"assets/logos/Default.png","team_colors":{1:"#000"}}
            with patch("generate_players.load_season_metadata",return_value=metadata),patch("generate_players.logo_config",return_value=config):
                build(source,output)
            career=json.loads((output/"players/1.json").read_text())
            self.assertEqual(career["career"]["starts"],1)
            self.assertEqual(career["career"]["FPTS"],10)
            self.assertEqual(career["fantasyEligibility"],["PG"])
            self.assertEqual(career["fantasyTeam"]["teamId"],1)
            self.assertEqual(career["gameSeasons"],[2026])
            self.assertEqual([game["date"] for game in career["gameLog"]],["2025-10-21","2025-10-20"])
            self.assertEqual([game["context"] for game in career["gameLog"]],["BENCH","START"])
            self.assertEqual(career["gameLog"][0]["FPTS"],10)
            self.assertEqual(career["gameLog"][0]["AST"],1)
            self.assertEqual(career["gameLog"][0]["team"]["logo"],"logos/One.png")
            self.assertEqual(career["transactions"][0]["type"],"DRAFTED")
            self.assertEqual(career["transactions"][0]["season"],2026)
            self.assertEqual(career["transactions"][0]["team"]["teamName"],"One")
            self.assertFalse(json.loads((output/"players.json").read_text())["players"][0]["active"])

    def test_game_log_keeps_inactive_played_rows_and_preserves_box_scores(self):
        daily=pd.DataFrame([
            {"Year":2025,"Scoring Period":1,"Date":"2024-10-20","Team Name":"One","Team ID":1,"Player Slot":"PG","FPTS":20,"MIN":30,"PTS":12,"REB":5,"AST":8,"STL":4,"BLK":0,"3PM":2,"TO":-4,"FGM":10,"FGA":-20,"FTM":3,"FTA":-4},
            {"Year":2026,"Scoring Period":2,"Date":"2025-10-22","Team Name":"Two","Team ID":2,"Player Slot":"IR","FPTS":30,"MIN":31,"PTS":14,"REB":6,"AST":10,"STL":8,"BLK":4,"3PM":3,"TO":-2,"FGM":12,"FGA":-22,"FTM":4,"FTA":-5},
            {"Year":2026,"Scoring Period":3,"Date":"2025-10-23","Team Name":"Two","Team ID":2,"Player Slot":"BE","FPTS":0,"MIN":0,"PTS":0,"REB":0,"AST":0,"STL":0,"BLK":0,"3PM":0,"TO":0,"FGM":0,"FGA":0,"FTM":0,"FTA":0},
        ])
        metadata={"seasons":[{"season":2025,"lineupSlots":["PG"]},{"season":2026,"lineupSlots":["PG"]}]}
        config={"team_logo_paths":{"One":"assets/logos/One.png","Two":"assets/logos/Two.png"},"default_logo_path":"assets/logos/Default.png","team_colors":{1:"#111",2:"#222"}}
        games,seasons=game_log(daily,metadata,config)
        self.assertEqual(seasons,[2026,2025])
        self.assertEqual([game["date"] for game in games],["2025-10-22","2024-10-20"])
        self.assertEqual(games[0]["context"],"INACTIVE")
        self.assertEqual((games[0]["FPTS"],games[0]["AST"],games[0]["STL"],games[0]["FGM"]),(30,5,2,6))

    def test_transactions_are_newest_first_and_pair_trade_teams(self):
        activity=pd.DataFrame([
            {"Year":2025,"Date":"2024-10-01","Time":"10:00","Team Name":"One","Action":"DRAFTED","Team ID":1,"Player ID":9},
            {"Year":2026,"Date":"2025-11-01","Time":"11:00","Team Name":"One","Action":"TRADED","Team ID":1,"Player ID":9},
            {"Year":2026,"Date":"2025-11-01","Time":"11:00","Team Name":"Two","Action":"RECEIVED","Team ID":2,"Player ID":9},
        ])
        config={"team_logo_paths":{"One":"assets/logos/One.png","Two":"assets/logos/Two.png"},"default_logo_path":"assets/logos/Default.png","team_colors":{1:"#111",2:"#222"}}
        events=transaction_history(activity,config)
        self.assertEqual([event["type"] for event in events],["RECEIVED","TRADED","DRAFTED"])
        self.assertEqual(events[0]["counterpartTeam"]["teamName"],"One")
        self.assertEqual(events[1]["counterpartTeam"]["teamName"],"Two")
        self.assertEqual(events[0]["team"]["logo"],"logos/Two.png")
        self.assertEqual(transaction_history(activity.iloc[0:0],config),[])


if __name__ == "__main__":
    unittest.main()
