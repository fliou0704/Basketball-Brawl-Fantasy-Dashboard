import unittest
from generate_scoreboard import project
from build_homepage import logo_config


class ScoreboardTests(unittest.TestCase):
    def setUp(self):
        self.current = {'season':2027,'week':2,'scoringPeriod':8,'teams':[{'teamId':i,'teamName':str(i)} for i in (1,2,3)]}
        self.mapping = [{'Year':2027,'Scoring Period':p,'Week':1 if p<8 else 2} for p in range(1,15)]
        self.calendar = {'season':2027,'dateAnchor':'2026-10-19','finalPeriod':28,'regularWeeks':2,
                         'weeks':[{'week':w,'start':'2026-10-20','end':'2026-10-26'} for w in (1,2,3,4)],
                         'matchups':[{'id':w,'week':w,'sides':[{'teamId':i,'pointsByPeriod':{'1':91,'8':0,'9':900}} for i in (1,2)]} for w in (1,2,3)]}
        self.rows = [{'Year':2027,'Week':1,'Team ID':i,'Team Name':str(i),'Type':'Regular','Opponent Team ID':3-i,'Points For':100+i} for i in (1,2)]

    def build(self):
        return project(self.current,[self.calendar],self.mapping,self.rows,logo_config())

    def test_first_day_uses_status_even_without_player_records(self):
        result=self.build()
        self.assertEqual(result['current']['week'],2)
        match=result['seasons'][0]['weeks'][1]['matchups'][0]
        self.assertEqual(match['status'],'current')
        self.assertEqual(match['actualScores'],[0,0])
        self.assertIsNone(match['winnerId'])

    def test_final_current_future_and_unpublished(self):
        weeks=self.build()['seasons'][0]['weeks']
        self.assertEqual(weeks[0]['matchups'][0]['actualScores'],[101,102])
        self.assertEqual(weeks[0]['matchups'][0]['winnerId'],2)
        self.assertEqual(weeks[2]['state'],'future')
        self.assertIsNone(weeks[2]['matchups'][0]['actualScores'])
        self.assertIsNone(weeks[2]['matchups'][0]['scoreDisplay'])
        self.assertEqual(weeks[3]['matchups'],[])

    def test_current_accumulation_filters_period_and_week(self):
        self.calendar['matchups'][1]['sides'][0]['pointsByPeriod']['8']=42
        self.assertEqual(self.build()['seasons'][0]['weeks'][1]['matchups'][0]['actualScores'],[42,0])

    def test_playoff_bye_and_unknown_team(self):
        self.calendar['matchups'].append({'id':30,'week':3,'sides':[{'teamId':3,'pointsByPeriod':{}}]})
        self.calendar['matchups'].append({'id':31,'week':3,'sides':[{'teamId':999,'pointsByPeriod':{}}]})
        self.rows.append({'Year':2027,'Week':3,'Team ID':3,'Team Name':'3','Type':'Bye','Opponent Team ID':'','Points For':'0'})
        playoff=self.build()['seasons'][0]['weeks'][2]
        self.assertEqual(playoff['phase'],'playoffs')
        self.assertEqual(len(playoff['matchups']),2)
        bye=playoff['matchups'][1]
        self.assertEqual(bye['status'],'bye')
        self.assertEqual(len(bye['teams']),1)
        self.assertIsNone(bye['actualScores'])

    def test_single_side_does_not_invent_a_bye(self):
        self.calendar['matchups'].append({'id':30,'week':3,'sides':[{'teamId':3,'pointsByPeriod':{}}]})
        match=self.build()['seasons'][0]['weeks'][2]['matchups'][-1]
        self.assertEqual(match['status'],'opponent-unavailable')
        self.assertFalse(match['bye'])
        self.assertIsNone(match['actualScores'])

    def test_missing_historical_scores_are_not_zero(self):
        self.rows=[]
        match=self.build()['seasons'][0]['weeks'][0]['matchups'][0]
        self.assertEqual(match['status'],'unavailable')
        self.assertIsNone(match['actualScores'])

    def test_completed_season_can_retain_terminal_status_week(self):
        self.current['scoringPeriod']=28
        self.current['week']=1
        match=self.build()['seasons'][0]['weeks'][0]
        self.assertEqual(match['state'],'final')
        self.assertEqual(match['matchups'][0]['actualScores'],[101,102])

    def test_mapping_disagreement_fails_explicitly(self):
        self.current['week']=1
        with self.assertRaisesRegex(ValueError,'disagree'):
            self.build()

    def test_previous_season_and_result_fallback(self):
        self.current['season']=2028
        self.current['week']=1
        self.calendar['matchups']=[]
        match=self.build()['seasons'][0]['weeks'][0]['matchups'][0]
        self.assertEqual(match['status'],'final')
        self.assertEqual(match['actualScores'],[101,102])


if __name__=='__main__':
    unittest.main()
