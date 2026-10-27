from copy import deepcopy
from datetime import datetime,timezone
import unittest
from fantasyOpportunities import remaining,potential_starts


def game(gid,day=8,home=1,away=2,status='scheduled',hour=23):
    return {'id':gid,'date':f'2026-10-{19+day:02d}','start':f'2026-10-{19+day:02d}T{hour:02d}:00:00+00:00',
            'home':home,'away':away,'status':status,'timeTBD':False,'regularSeason':True,'period':day}


class OpportunitiesTests(unittest.TestCase):
    def setUp(self):
        self.week={'week':2,'state':'current','dateRangeKind':'scheduled','firstPeriod':7,'lastPeriod':13,'start':'2026-10-26','end':'2026-11-01'}
        from datetime import date,timedelta
        self.calendar={'season':2027,'lineupSlots':['PG','UT'],'scheduledDays':[{'period':p,'week':2,'date':(date(2026,10,19)+timedelta(days=p)).isoformat()}for p in range(7,14)]}
        self.current={'season':2027,'updatedAt':'2026-10-27T16:00:00Z','lineupConstraints':{'daily':True,'rosterLock':'FIRSTGAME_SCORINGPERIOD','slotStatLimits':{}},
            'teams':[{'teamId':1,'roster':[{'playerId':10,'name':'One','proTeamId':1,'eligibility':['PG','UT'],'slot':'BE'},
                                        {'playerId':20,'name':'Two','proTeamId':1,'eligibility':['PG'],'slot':'PG'},
                                        {'playerId':30,'name':'Three','proTeamId':1,'eligibility':['UT'],'slot':'BE'}]}]}
        self.schedule={'schemaVersion':2,'season':2027,'publishedComplete':True,'verifiedAt':'2026-10-27T12:00:00Z',
            'teams':[{'id':1},{'id':2},{'id':3}], 'rules':{'expectedTeamGames':1,'cupWindow':['2026-12-04','2026-12-10']},'fixtures':[game(1)]}
        for p in self.current['teams'][0]['roster']:
            p.update(nbaTeamSince='2026-10-20T00:00:00Z',rosterSince='2026-10-20T00:00:00Z')
    def result(self,**kw):return remaining(self.current,self.calendar,self.week,1,self.schedule,**kw)

    def test_slot_conflicts_and_game_identity_not_duplicated(self):
        r=self.result();self.assertEqual(r['games'],3);self.assertEqual(r['potentialStarts'],2)
        self.schedule['fixtures'].append(deepcopy(self.schedule['fixtures'][0]))
        self.assertEqual(self.result()['games'],3)

    def test_ir_bench_eligibility_dnp_are_opportunities_not_appearances(self):
        self.current['teams'][0]['roster'][0]['slot']='IR'
        self.current['teams'][0]['roster'][1]['slot']='IR'
        r=self.result();self.assertEqual(r['games'],3);self.assertEqual(r['potentialStarts'],1)
        self.assertNotIn('actualStarts',r)

    def test_current_lineup_occupied_slots_in_progress_and_not_yet_scored(self):
        self.schedule['fixtures'] += [game(2,home=3,away=2,status='in-progress',hour=12)]
        self.current['teams'][0]['roster'][1]['proTeamId']=3
        r=self.result();self.assertEqual(r['games'],2);self.assertEqual(r['inProgress'],1);self.assertEqual(r['potentialStarts'],1)
        self.schedule['fixtures'][1]['status']='scheduled' # past start, status not confirmed
        r=self.result();self.assertEqual(r['games'],2);self.assertEqual(r['startedUnconfirmed'],1)

    def test_dropped_historical_starter_reserves_slot_without_current_affiliation(self):
        r=self.result(locked=[{'playerId':999,'slot':'PG','date':'2026-10-27'}])
        self.assertEqual(r['potentialStarts'],1)

    def test_trade_does_not_assign_destination_teams_past_game_to_player(self):
        self.schedule['fixtures'].append(game(2,home=3,away=2,status='completed',hour=12))
        p=self.current['teams'][0]['roster'][1]
        p.update(proTeamId=3,nbaTeamSince='2026-10-27T15:00:00Z')
        r=self.result()
        self.assertEqual(r['games'],2)
        self.assertEqual(r['potentialStarts'],2)  # no fabricated earlier PG lock

    def test_duplicate_fantasy_roster_is_unavailable_not_double_counted(self):
        self.current['teams'][0]['roster'].append(deepcopy(self.current['teams'][0]['roster'][0]))
        self.assertIsNone(self.result()['games'])

    def test_nba_trade_and_fantasy_add_drop_only_change_future_associations(self):
        before=deepcopy(self.schedule)
        self.current['teams'][0]['roster'][0]['proTeamId']=3
        self.assertEqual(self.result()['games'],2)
        self.current['teams'][0]['roster'].pop()
        self.assertEqual(self.result()['games'],1)
        self.assertEqual(self.schedule,before)
        self.current['teams'][0]['roster'][0]['proTeamId']=0 # verified free agent
        self.assertEqual(self.result()['players'][0]['gameIds'],[])

    def test_unknown_affiliation_stale_or_partial_source_is_not_zero(self):
        self.current['teams'][0]['roster'][0]['proTeamId']=None
        self.assertIsNone(self.result()['games']);self.assertIsNone(self.result()['potentialStarts'])
        self.current['teams'][0]['roster'][0]['proTeamId']=1
        self.schedule['publishedComplete']=False;self.assertIsNone(self.result()['games'])
        self.schedule['publishedComplete']=True;self.schedule['verifiedAt']='2026-10-25T00:00:00Z'
        self.assertIsNone(self.result()['games'])

    def test_time_tbd_tomorrow_is_dated_but_time_tbd_today_is_unavailable(self):
        self.schedule['fixtures'][0].update(date='2026-10-28',start='2026-10-28T23:00:00Z',status='tbd',timeTBD=True)
        self.assertEqual(self.result()['games'],3)
        self.schedule['fixtures'][0].update(date='2026-10-27',start='2026-10-27T23:00:00Z')
        self.assertIsNone(self.result()['games'])
        self.schedule['fixtures'][0].update(status='scheduled',statusVerifiedAt=self.current['updatedAt'])
        self.assertEqual(self.result()['games'],3)

    def test_status_failure_only_blocks_affected_current_day(self):
        self.schedule['statusError']='unavailable'
        self.assertIsNone(self.result()['games'])
        self.schedule['fixtures'][0].update(date='2026-10-28',start='2026-10-28T23:00:00Z')
        self.assertEqual(self.result()['games'],3)

    def test_resumed_game_is_not_a_second_future_start(self):
        self.schedule['fixtures'][0]['hasStarted']=True
        r=self.result()
        self.assertEqual(r['games'],0);self.assertIsNone(r['potentialStarts']);self.assertTrue(r['uncertain'])

    def test_cup_unknown_dates_count_confirmed_only_and_withhold_potential(self):
        self.schedule['rules']['cupWindow']=['2026-10-26','2026-11-01'];self.schedule['rules']['expectedTeamGames']=2
        r=self.result();self.assertEqual(r['games'],3);self.assertTrue(r['uncertain']);self.assertIsNone(r['potentialStarts'])
        self.assertTrue(r['days'][0]['additionalTBD'])
        self.schedule['rules']['cupWindow']=['2026-12-04','2026-12-10']
        self.assertEqual(self.result()['potentialStarts'],2)

    def test_postponed_canceled_and_cup_championship_are_not_future_games(self):
        self.schedule['fixtures'][0]['status']='postponed'
        r=self.result();self.assertEqual(r['games'],0);self.assertTrue(r['uncertain']);self.assertIsNone(r['potentialStarts'])
        self.schedule['fixtures'][0]['status']='canceled'
        self.assertEqual(self.result()['games'],0)
        self.schedule['fixtures'][0]['regularSeason']=False
        self.assertEqual(self.result()['games'],0)

    def test_weekly_locks_or_limits_suppress_starts_but_keep_confirmed_games(self):
        for field,val in [('daily',False),('slotStatLimits',{'PG':82}),('rosterLock','FIRSTGAME_WEEKLY'),('moveLimit',0)]:
            current=deepcopy(self.current);self.current['lineupConstraints'][field]=val
            r=self.result();self.assertEqual(r['games'],3);self.assertIsNone(r['potentialStarts']);self.current=current
        self.current['teams'][0]['roster'][0].pop('eligibility')
        self.assertEqual(self.result()['games'],3);self.assertIsNone(self.result()['potentialStarts'])

    def test_future_and_extended_playoff_calendar_uses_date_join(self):
        self.week.update(week=21,state='future',firstPeriod=147,lastPeriod=160,start='2027-03-15',end='2027-03-28')
        from datetime import date,timedelta
        self.calendar['scheduledDays']=[{'period':147+i,'date':(date(2027,3,15)+timedelta(days=i)).isoformat(),'week':21}for i in range(14)]
        self.schedule['fixtures'][0].update(date='2027-03-28',start='2027-03-28T23:00:00Z')
        r=self.result();self.assertEqual(r['games'],3);self.assertEqual(len(r['days']),14)
        self.week['state']='final';r=self.result();self.assertEqual(r['games'],0);self.assertEqual(r['potentialStarts'],0)


if __name__=='__main__':unittest.main()
