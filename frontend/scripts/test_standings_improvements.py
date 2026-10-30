import unittest
import json
import os
from pathlib import Path
from generate_standings import all_play
from build_homepage import standings_charts
from playerDailyAggregation import load_season_metadata


class AllPlayTests(unittest.TestCase):
    def setUp(self):
        self.teams={i:{'teamId':i,'teamName':f'Historical {i}'} for i in range(1,5)}
    def rows(self,week,values,kind='Regular'):
        return [{'Week':week,'Team ID':i+1,'Points For':v,'Type':kind,'Rank':i+1} for i,v in enumerate(values)]
    def test_ties_symmetry_ranking_and_official_scores(self):
        rows=self.rows(1,[100,100,50,0])+self.rows(2,[0,10,20,30])
        result=all_play(rows,self.teams,[1,2]);teams={t['teamId']:t for t in result['teams']}
        self.assertEqual((teams[1]['wins'],teams[1]['losses'],teams[1]['ties']),(2,3,1))
        self.assertEqual(teams[1]['winPct'],2.5/6)
        self.assertEqual(sum(t['wins'] for t in teams.values()),sum(t['losses'] for t in teams.values()))
        self.assertEqual(result['teams'][0]['teamId'],2)
        self.assertEqual(teams[1]['teamName'],'Historical 1')
    def test_incomplete_playoff_bye_duplicate_future_and_nonfinite_excluded(self):
        rows=self.rows(1,[1,2,3,4])+self.rows(2,[9,8])+self.rows(3,[1,2,3,4],'Playoffs')+self.rows(4,[1,2,3,4],'Bye')+self.rows(5,[1,2,3,4])+self.rows(6,[1,2,float('nan'),4])
        rows+=self.rows(7,[1,2,3,4])+self.rows(7,[1])
        self.assertEqual(all_play(rows,self.teams,[1,2,3,4,6,7])['weeks'],[1])
    def test_chart_full_verified_season_axis_and_empty_future_positions(self):
        rows=self.rows(1,[100,90,80,70])
        chart=standings_charts({1:rows},self.teams,[1],list(range(1,21)))
        self.assertEqual(len(chart['scoringWeekTicks']),20)
        self.assertEqual(len(chart['highWeeks']),1)
        self.assertLess(chart['highWeeks'][0]['width'],30)

    def test_generated_axes_use_regular_length_even_when_observed_calendar_is_partial(self):
        output=Path(os.environ.get('FRONTEND_TEST_OUTPUT',Path(__file__).resolve().parents[1]/'public/data'))
        for season in load_season_metadata()['seasons']:
            chart=json.loads((output/str(season['season'])/'history.json').read_text())['data']['standingsCharts']
            self.assertEqual([t['week'] for t in chart['scoringWeekTicks']],list(range(1,season['regularWeeks']+1)))
