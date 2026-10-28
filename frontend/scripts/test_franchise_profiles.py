import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
import pandas as pd
from generate_franchise_profiles import build, franchise_profile
from generate_record_book import completed_season_years


class FranchiseProfileTests(unittest.TestCase):
    def setUp(self):
        self.config={'team_logo_paths':{'Old name':'assets/logos/old.png','New name':'assets/logos/new.png'},
                     'default_logo_path':'assets/logos/Default.png','team_colors':{7:'#123456',8:'#654321'}}
        rows=[]
        for year,name in ((2025,'Old name'),(2026,'New name')):
            for team in (7,8):
                rows.extend([{'Year':year,'Week':1,'Team ID':team,'Team Name':name if team==7 else 'Other',
                              'Team Owner':'Former owner' if year==2025 else 'New owner','Type':'Regular',
                              'Win':int(team==7),'Loss':int(team==8),'Points For':100 if team==7 else 80,
                              'Points Against':80 if team==7 else 100,'Rank':1 if team==7 else 2},
                             {'Year':year,'Week':2,'Team ID':team,'Team Name':name if team==7 else 'Other',
                              'Team Owner':'Former owner' if year==2025 else 'New owner','Type':'Playoffs',
                              'Win':int(team==7),'Loss':int(team==8),'Points For':110 if team==7 else 90,
                              'Points Against':90 if team==7 else 110,'Rank':1 if team==7 else 2}])
        self.league=pd.DataFrame(rows)
        self.metadata={'seasons':[{'season':year,'regularWeeks':1,'finalPeriod':14,
                                  'weeks':[{'week':1,'lastPeriod':7},{'week':2,'lastPeriod':14}]} for year in (2025,2026)]}
        self.payload={'team':{'teamId':7,'teamName':'New name','logo':'logos/new.png','color':'#123456','owner':'New owner'},
                      'summary':{'performance':{'fpPerStart':None}},'seasons':{str(year):{
                          'snapshot':{'wins':1,'losses':0,'pointsFor':100,'rank':1},
                          'performance':{'season':{'fpPerStart':30 if year==2025 else None}}} for year in (2025,2026)}}

    def test_renames_and_owner_changes_keep_franchise_id_and_historical_assets(self):
        profile=franchise_profile(self.payload,self.league,{2025},self.metadata,self.config)
        old,new=profile['history'][1],profile['history'][0]
        self.assertEqual(old['team']['teamName'],'Old name')
        self.assertEqual(old['team']['logo'],'logos/old.png')
        self.assertEqual(new['team']['teamId'],old['team']['teamId'])
        self.assertEqual(old['owners'],['Former owner'])
        self.assertEqual(new['owners'],['New owner'])
        self.assertEqual(profile['totals']['fpts'],420)
        self.assertEqual(profile['totals']['wins'],2)

    def test_partial_season_never_awarded_title_appearance_or_final_rank(self):
        profile=franchise_profile(self.payload,self.league,{2025},self.metadata,self.config)
        self.assertEqual(profile['totals']['championships'],1)
        self.assertEqual(profile['totals']['championshipAppearances'],1)
        self.assertEqual(profile['totals']['playoffAppearances'],1)
        self.assertEqual(profile['history'][0]['playoffFinish'],'In progress')
        self.assertIsNone(profile['history'][0]['finalRank'])
        self.assertEqual(profile['history'][1]['playoffFinish'],'Champion')
        self.assertEqual(profile['bestSeason'],2025)
        self.assertEqual(profile['worstSeason'],2025)
        self.assertEqual([item['year'] for item in profile['achievements']],[2025])

    def test_completion_and_finalists_reuse_record_book_semantics(self):
        daily=pd.DataFrame([{'Year':2025,'Scoring Period':14},{'Year':2026,'Scoring Period':7}])
        completed=completed_season_years(self.league,daily,self.metadata)
        self.assertEqual(completed,[2025])
        other={**self.payload,'team':{**self.payload['team'],'teamId':8}}
        profile=franchise_profile(other,self.league,set(completed),self.metadata,self.config)
        self.assertEqual(profile['history'][1]['playoffFinish'],'Runner-up')
        self.assertEqual(profile['totals']['championships'],0)
        self.assertEqual(profile['totals']['championshipAppearances'],1)

    def test_trends_preserve_missing_efficiency_and_reverse_rank_axis(self):
        profile=franchise_profile(self.payload,self.league,{2025},self.metadata,self.config)
        trend=profile['trends']['fpPerStart']
        self.assertEqual(trend['points'][0]['value'],30)
        self.assertIsNone(trend['points'][1]['y'])
        self.assertTrue(trend['points'][1]['partial'])
        rank=profile['trends']['regularRank']
        self.assertLess(rank['ticks'][0]['y'],rank['ticks'][-1]['y'])
        self.assertIsNone(profile['totals']['fpPerStart'])

    def test_export_only_adds_profile_and_preserves_existing_summary_and_seasons(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'team-stats').mkdir()
            self.league.to_csv(root/'basketballBrawlLeagueData.csv',index=False)
            pd.DataFrame([{'Year':2025,'Scoring Period':14}]).to_csv(root/'playerDailyData.csv',index=False)
            target=root/'team-stats/7.json'
            target.write_text(json.dumps(self.payload))
            with patch('generate_franchise_profiles.load_season_metadata',return_value=self.metadata), patch('generate_franchise_profiles.logo_config',return_value=self.config):
                build(root,root)
            exported=json.loads(target.read_text())
            self.assertEqual(exported['summary'],self.payload['summary'])
            self.assertEqual(exported['seasons'],self.payload['seasons'])
            self.assertEqual(exported['franchise']['totals']['seasons'],2)
