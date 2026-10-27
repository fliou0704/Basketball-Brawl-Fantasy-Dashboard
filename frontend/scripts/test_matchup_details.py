import copy
import unittest
from generate_matchup_details import matchup_detail, potential_starts, remaining_opportunities, stable_key


class DetailTests(unittest.TestCase):
    def setUp(self):
        self.current = {'season':2027,'scoringPeriod':3,'updatedAt':'2026-10-26T16:00:00Z','teams':[{'teamId':1,'roster':[{'playerId':11,'name':'11'}]}]}
        self.calendar = {'season':2027,'dateAnchor':'2026-10-19','lineupSlots':['PG','UT'], 'scoringWeights':{'PTS':1,'AST':2},
                         'matchups':[{'id':1,'sides':[{'teamId':1,'pointsByPeriod':{'1':10,'2':0,'3':5}}, {'teamId':2,'pointsByPeriod':{'1':5,'2':10,'3':0}}]}]}
        self.match = {'id':1,'teams':[{'teamId':1},{'teamId':2}],'actualScores':[15,15]}
        self.week = {'week':1,'state':'final','dateRangeKind':'observed'}
        self.rows = [self.row(1,1,11,10),self.row(1,2,22,5),self.row(2,2,22,10),self.row(3,1,33,5)]

    def row(self,p,t,pid,points,slot='UT',minutes=20):
        return {'Scoring Period':p,'Team ID':t,'Player ID':pid,'Player Name':str(pid),'Player Slot':slot,'MIN':minutes,'FPTS':points,'PTS':points,'AST':2}

    def detail(self):
        return matchup_detail(self.match,self.week,self.calendar,self.current,{p:1 for p in (1,2,3)},self.rows)

    def test_daily_reconciles_and_ties_retain_prior_leader(self):
        d=self.detail()
        self.assertTrue(d['reconciled'])
        self.assertEqual([p['cumulative'] for p in d['days']],[[10,5],[10,15],[15,15]])
        self.assertEqual(d['insights']['leadChanges'],1)
        self.assertEqual(d['insights']['comebacks'],[5,5])
        self.assertEqual(d['insights']['largestDailyAdvantage']['margin'],10)
        self.assertEqual(d['completedStarts'],[2,2])

    def test_bench_ir_and_zero_minutes_do_not_inflate_starts(self):
        self.rows += [self.row(1,1,44,100,'BE'),self.row(1,1,55,100,'IR'),self.row(2,1,66,0,minutes=0)]
        d=self.detail()
        self.assertEqual(d['completedStarts'],[2,2])
        self.assertTrue(d['reconciled'])
        self.assertNotIn(44,[p['playerId'] for p in d['players']])

    def test_missing_period_is_unknown_not_zero(self):
        self.calendar['matchups'][0]['sides'][0]['pointsByPeriod'].pop('2')
        d=self.detail()
        self.assertIsNone(d['days'][1]['points'][0])
        self.assertIsNone(d['days'][2]['cumulative'][0])
        self.assertIsNone(d['insights'])

    def test_corrections_withhold_insights_instead_of_adjusting_daily_points(self):
        self.match['actualScores']=[100,15]
        self.assertFalse(self.detail()['reconciled'])
        self.assertIsNone(self.detail()['insights'])
        self.assertEqual(self.detail()['days'][-1]['cumulative'],[15,15])

    def test_future_no_fake_scores_and_completed_zero_remaining(self):
        self.week['state']='future';self.match['actualScores']=None
        d=self.detail()
        self.assertEqual(d['days'],[])
        self.assertIsNone(d['remaining'][0]['games'])
        self.week['state']='final'
        self.assertEqual(self.detail()['remaining'][0]['games'],0)

    def test_roster_changes_preserve_historical_team_and_current_membership(self):
        self.week['state']='current'
        d=self.detail()
        self.assertTrue(next(p for p in d['players'] if p['playerId']==11)['currentRoster'])
        self.assertFalse(next(p for p in d['players'] if p['playerId']==33)['currentRoster'])
        self.rows.append(self.row(2,2,11,4));self.match['actualScores'][1]+=4
        self.assertEqual(len([p for p in self.detail()['players'] if p['playerId']==11]),2)
        self.week['state']='final'
        self.assertTrue(all(p['currentRoster'] is None for p in self.detail()['players']))

    def test_rename_and_source_id_changes_do_not_change_route(self):
        self.assertEqual(stable_key([{'teamId':2,'teamName':'New'},{'teamId':1}]),'1-2')

    def test_eligibility_matching_reassigns_flexible_players_and_excludes_ir(self):
        players=[{'eligibility':['PG','UT']},{'eligibility':['UT']},{'eligibility':['PG'],'slot':'IR'}]
        self.assertEqual(potential_starts(players,['UT','PG']),2)
        self.assertEqual(potential_starts(players,['PG']),1)
        self.assertEqual(potential_starts([],['PG']),0)

    def test_irregular_and_multiday_playoff_periods_are_not_truncated(self):
        self.week['state']='final';self.calendar['season']=2026
        self.current['season']=2027
        d=matchup_detail(self.match,self.week,self.calendar,self.current,{p:1 for p in range(1,15)},self.rows)
        self.assertEqual(len(d['days']),14)
        self.assertEqual(d['days'][-1]['date'],'2026-11-02')

    def test_offsetting_daily_corrections_still_withhold_lead_insights(self):
        self.calendar['matchups'][0]['sides'][0]['pointsByPeriod'].update({'1':11,'3':4})
        self.assertEqual(self.detail()['days'][-1]['cumulative'],[15,15])
        self.assertFalse(self.detail()['reconciled'])

    def test_current_unfinished_period_is_excluded_from_lead_insights(self):
        self.week['state']='current'
        d=self.detail()
        self.assertTrue(d['days'][-1]['partial'])
        self.assertEqual(d['insights']['comebacks'],[0,5])

    def test_duplicate_daily_rows_fail(self):
        self.rows.append(self.rows[0])
        with self.assertRaisesRegex(ValueError,'Duplicate'):self.detail()


class RemainingTests(unittest.TestCase):
    def setUp(self):
        self.week={'state':'current','dateRangeKind':'scheduled','firstPeriod':7,'lastPeriod':10}
        self.calendar={'dateAnchor':'2026-10-19','lineupSlots':['PG']}
        self.current={'updatedAt':'2026-10-26T16:00:00Z','lineupConstraints':{'daily':True},
                      'teams':[{'teamId':1,'roster':[{'playerId':1,'name':'One','proTeamId':1,'eligibility':['PG']},{'playerId':2,'name':'Two','proTeamId':1,'eligibility':['PG']}]}],
                      'nbaSchedule':{'complete':True,'games':[
                          {'id':1,'proTeamId':1,'period':7,'start':'2026-10-26T12:00:00Z','state':'completed'},
                          {'id':2,'proTeamId':1,'period':7,'start':'2026-10-26T15:00:00Z','state':'started-unconfirmed'},
                          {'id':3,'proTeamId':1,'period':8,'start':'2026-10-27T23:00:00Z','state':'scheduled'},
                          {'id':4,'proTeamId':1,'period':10,'start':'2026-10-29T23:00:00Z','state':'scheduled'},
                          {'id':5,'proTeamId':1,'period':11,'start':'2026-10-30T23:00:00Z','state':'scheduled'}]}}

    def result(self):return remaining_opportunities(self.current,self.calendar,self.week,1)

    def test_games_starts_zero_days_and_started_games_are_distinct(self):
        result=self.result()
        self.assertEqual(result['games'],4)
        self.assertEqual(result['potentialStarts'],2)
        self.assertEqual([d['games'] for d in result['days']],[0,2,0,2])
        self.assertEqual(result['days'][0]['inProgress'],2)
        self.assertEqual(len(result['players'][0]['games']),2)

    def test_dedup_ir_and_zero_game_roster_members(self):
        self.current['nbaSchedule']['games'].append(copy.deepcopy(self.current['nbaSchedule']['games'][2]))
        self.current['teams'][0]['roster'][0]['slot']='IR'
        self.assertEqual(self.result()['games'],4)
        self.assertEqual(self.result()['potentialStarts'],2)
        self.current['teams'][0]['roster'][1]['proTeamId']=9
        self.assertEqual(self.result()['games'],2)
        self.assertEqual(self.result()['potentialStarts'],0)

    def test_missing_bounds_schedule_identity_and_locks_fail_closed(self):
        for kind in ('observed','unavailable'):
            self.week['dateRangeKind']=kind
            self.assertIsNone(self.result()['games'])
        self.week['dateRangeKind']='scheduled'
        self.current['nbaSchedule']['complete']=False
        self.assertIsNone(self.result()['games'])
        self.current['nbaSchedule']['complete']=True
        self.current['lineupConstraints']['daily']=False
        self.assertIsNone(self.result()['potentialStarts'])
        self.current['teams'][0]['roster'][0].pop('proTeamId')
        self.assertIsNone(self.result()['games'])

    def test_new_york_date_boundary_retains_previous_local_day(self):
        self.current['updatedAt']='2026-10-27T01:00:00Z'
        self.assertEqual(self.result()['days'][0]['date'],'2026-10-26')

if __name__=='__main__':unittest.main()
