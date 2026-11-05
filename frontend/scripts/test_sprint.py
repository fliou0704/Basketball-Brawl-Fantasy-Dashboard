import json
from pathlib import Path
import tempfile
import unittest
from build_homepage import standings_charts, ROOT
from generate_top150 import build, validate_pool
from generate_record_book import build as record_book


class SprintTests(unittest.TestCase):
    def test_rank_weeks_include_playoffs_and_byes_without_changing_ranks(self):
        teams={i:{'teamId':i,'teamName':str(i),'logo':f'logos/{i}.png'} for i in [1,2]}
        weeks={w:[{'Team ID':i,'Type':'Regular' if w==1 else 'Playoffs','Rank':3-i,'Points For':100+i} for i in teams] for w in [1,2,3]}
        chart=standings_charts(weeks,teams,[1,2,3],[1,2,3])
        self.assertEqual(chart['weeks'],[1,2,3])
        self.assertEqual(chart['ranks'][0]['points'][-1]['x'],770)
        self.assertTrue(all(b['logo']==f"logos/{b['teamId']}.png" for b in chart['highWeeks']))
        self.assertEqual(chart['ranks'][0]['points'][-1]['rank'],2)

    def test_pool_validation_rejects_incomplete_wrong_scoring_and_duplicates(self):
        pool={'complete':True,'source':'fixture','scope':'NBA regular season','scoringWeights':{'PTS':1},
              'players':[{'playerId':i,'name':str(i),'fpts':100,'gp':40} for i in range(1,152)]}
        self.assertEqual(len(validate_pool(pool,{'PTS':1})),151)
        for invalid in [{**pool,'complete':False},{**pool,'scoringWeights':{}},
                        {**pool,'players':pool['players']+[pool['players'][0]]},
                        {**pool,'maxTeamGames':20}]:
            with self.assertRaises(ValueError):validate_pool(invalid,{'PTS':1})

    def test_real_export_is_honest_about_pool_and_stat_gaps(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)
            payload=build(ROOT/'data',target)
            self.assertTrue(all(not s['completePool'] for s in payload['seasons'].values()))
            records=record_book(ROOT/'data',target)
            import pandas as pd
            daily=pd.read_csv(ROOT/'data/playerDailyData.csv')
            daily['_game_date']=pd.to_datetime(daily['Date']).dt.strftime('%m/%d/%Y')
            games=daily.set_index(['Player ID','_game_date'])
            for row in records['allTime']['hundredPointDays']:
                source=games.loc[[(row['Player ID'],row['Date'])]].iloc[0]
                self.assertEqual(row['FPTS'],source['FPTS'])
                self.assertEqual(row['stats']['AST'],source['AST']/2)
                self.assertEqual(row['stats']['TO'],source['TO']/-2)
                self.assertIsNone(row['stats']['3PA'])

if __name__=='__main__':unittest.main()
