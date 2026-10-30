from copy import deepcopy
from datetime import datetime, timezone
import unittest
from matchupProjections import optimal_lineup, trailing_average, normalize_history, project_team, historical_potential, refresh_history

STAMP='2026-10-30T16:00:00+00:00'

def history(points,day='2026-10-29',gid=1,season=2027):
    return {'gameId':gid,'season':season,'date':day,'points':points,'completed':True,'knownAt':STAMP}

def player(pid,points,eligibility,slot='BE'):
    return {'playerId':pid,'name':str(pid),'points':points,'eligibility':eligibility,'slot':slot}

class AverageTests(unittest.TestCase):
    def test_cross_season_trailing_ten_excludes_future_and_incomplete(self):
        games=[history(i,f'2026-04-{i:02d}',i,2026) for i in range(1,13)]
        games+=[history(100,'2026-10-30',50),history(1000,'2026-10-31',51),dict(history(200,'2026-10-29',52),completed=False)]
        sample=trailing_average(games,'2026-10-30',STAMP)
        self.assertEqual(sample['sampleSize'],10);self.assertEqual(sample['points'],7.5)
    def test_zero_negative_fewer_and_snapshot_no_leakage(self):
        games=[history(0,gid=1),history(-4,gid=2),dict(history(100,gid=3),knownAt='2026-10-31T00:00:00Z')]
        self.assertEqual(trailing_average(games,'2026-10-31',STAMP)['points'],-2)
        self.assertEqual(trailing_average(games,'2026-10-31',STAMP)['sampleSize'],2)
        self.assertIsNone(trailing_average([],'2026-10-31',STAMP)['points'])
    def test_duplicate_games_deduplicate_and_conflicts_are_unavailable(self):
        game=history(10);self.assertEqual(trailing_average([game,game],'2026-10-31',STAMP)['sampleSize'],1)
        self.assertIsNone(trailing_average([game,dict(game,points=20)],'2026-10-31',STAMP)['points'])
    def test_bulk_actuals_require_completion_game_ids_and_exclude_dnp(self):
        def raw(gid,season,p,minutes=20,total=10,source=0):
            return {'externalId':str(gid),'seasonId':season,'scoringPeriodId':p,'statSourceId':source,'statSplitTypeId':5,'stats':{'40':minutes},'appliedTotal':total}
        data={'players':[{'player':{'id':1,'stats':[raw(1,2027,10,total=0),raw(2,2027,11),raw(3,2026,170,total=-2),raw(4,2026,171,minutes=0),raw(5,2027,12,source=1)]}}]}
        schedules={'2027':{'fixtures':[{'id':1,'season':2027,'period':10,'date':'2026-10-29','start':'2026-10-29T23:00:00Z','status':'completed'},{'id':2,'season':2027,'period':11,'date':'2026-10-30','start':'2026-10-30T15:00:00Z','status':'in-progress'}]}}
        calendar=[{'season':2027,'dateAnchor':'2026-10-19'},{'season':2026,'dateAnchor':'2025-10-20'}]
        result=normalize_history(data,{1},calendar,schedules,datetime.fromisoformat(STAMP))
        self.assertEqual([g['points'] for g in result['1']['games']],[0,-2])
        self.assertEqual(result['1']['games'][1]['date'],'2026-04-08')

    def test_invalid_samples_do_not_become_zero_estimates(self):
        self.assertIsNone(trailing_average([dict(history(1),points=None)],'2026-10-31',STAMP)['points'])
        self.assertIsNone(trailing_average([dict(history(1),knownAt='bad')],'2026-10-31',STAMP)['points'])

class BulkRefreshTests(unittest.TestCase):
    def test_historical_endpoint_is_bulk_and_cached_across_updates(self):
        from types import SimpleNamespace
        calls=[]
        def row(gid,season,period):
            return {'externalId':str(gid),'seasonId':season,'scoringPeriodId':period,'statSourceId':0,'statSplitTypeId':5,'stats':{'40':20},'appliedTotal':10}
        live={'players':[{'player':{'id':1,'stats':[row(1,2027,10)]}}]}
        old={'players':[{'player':{'id':1,'stats':[row(i+2,2025,100+i)for i in range(12)]}}]}
        class Request:
            def __init__(self,season):self.season=season
            def get_player_card(self,ids,*args,**kwargs):
                calls.append((self.season,ids));return live if self.season==2027 else old
        league=SimpleNamespace(year=2027,finalScoringPeriod=167,teams=[SimpleNamespace(roster=[SimpleNamespace(playerId=1)])],espn_request=Request(2027))
        calendars=[{'season':2027,'dateAnchor':'2026-10-19'},{'season':2026,'dateAnchor':'2025-10-20'},{'season':2025,'dateAnchor':'2024-10-21'}]
        fixtures={'2027':{'fixtures':[{'id':1,'season':2027,'period':10,'date':'2026-10-29','start':'2026-10-29T23:00:00Z','status':'completed'}]}}
        first=refresh_history(league,calendars,fixtures,datetime.fromisoformat(STAMP),request_factory=Request)
        self.assertEqual(calls,[(2027,[1]),(2025,[1])]);self.assertEqual(len(first['players']['1']['games']),13)
        calls.clear()
        again=refresh_history(league,calendars,fixtures,datetime.fromisoformat(STAMP),previous=first,request_factory=Request)
        self.assertEqual(calls,[(2027,[1])]);self.assertEqual(again['players']['1']['games'],first['players']['1']['games'])

class OptimizationTests(unittest.TestCase):
    def test_positional_conflicts_reassignment_and_cap_ten(self):
        pool=[player(1,100,['PG','UT']),player(2,90,['PG']),player(3,80,['UT'])]
        best=optimal_lineup(pool,['PG','UT']);self.assertEqual(best['points'],190)
        self.assertEqual(best['assignments'],{1:'UT',2:'PG'})
        self.assertEqual(len(optimal_lineup([player(i,i,['UT']) for i in range(1,14)],['UT']*12)['assignments']),10)
    def test_ir_negative_zero_bench_and_deterministic_ties(self):
        pool=[player(1,100,['PG'],'IR'),player(2,-5,['PG']),player(3,0,['PG']),player(4,0,['PG'])]
        best=optimal_lineup(pool,['PG']);self.assertEqual(best['points'],0);self.assertEqual(best['assignments'],{3:'PG'})
    def test_missing_values_eligibility_and_duplicates_fail(self):
        for pool in ([player(1,None,['PG'])],[player(1,10,[])],[player(1,10,['PG']),player(1,10,['PG'])]):
            with self.assertRaises(ValueError):optimal_lineup(pool,['PG'])
    def test_potential_complete_roster_bench_ir_and_membership(self):
        records=[dict(player(1,10,['PG'],'PG'),gameComplete=True,rosterMember=True),dict(player(2,30,['PG']),gameComplete=True,rosterMember=True),dict(player(3,100,['PG'],'IR'),gameComplete=True,rosterMember=True),dict(player(4,200,['PG']),gameComplete=True,rosterMember=False)]
        result=historical_potential(records,['PG'],10,complete=True,locks_verified=True)
        self.assertEqual(result['points'],30);self.assertEqual(result['leftOnBench'],20);self.assertAlmostEqual(result['efficiency'],1/3)
        self.assertIsNone(historical_potential(records,['PG'],10)['points'])
        self.assertIsNone(historical_potential(records,['PG'],40,complete=True,locks_verified=True)['points'])
    def test_zero_potential_efficiency_and_incomplete_eligibility(self):
        record=dict(player(1,-1,['PG']),gameComplete=True,rosterMember=True)
        result=historical_potential([record],['PG'],0,complete=True,locks_verified=True)
        self.assertEqual(result['points'],0);self.assertIsNone(result['efficiency'])
        record['eligibility']=[]
        self.assertIsNone(historical_potential([record],['PG'],0,complete=True,locks_verified=True)['points'])

class ProjectionTests(unittest.TestCase):
    def test_fresh_same_day_out_exclusion_reoptimizes_bench_without_erasing_average(self):
        self.fixtures[10]['date']='2026-10-30';self.opps['days'][0]['date']='2026-10-30'
        p=self.team['roster'][0];p.update(injuryStatus='OUT',injuryVerifiedAt=STAMP,injurySource='ESPN current roster')
        result=self.result();self.assertEqual(result['remaining'],10)
        first=result['days'][0]['players'][0]
        self.assertEqual(first['points'],20);self.assertTrue(first['excluded']);self.assertFalse(first['selected'])
        for status in ['QUESTIONABLE','DOUBTFUL','DAY_TO_DAY','ACTIVE',None]:
            p['injuryStatus']=status;self.assertEqual(self.result()['remaining'],20)
        p['injuryStatus']='SSPD';self.assertEqual(self.result()['remaining'],10)
        p['injuryStatus']='OUT';p['injuryVerifiedAt']='2026-10-29T01:00:00Z'
        self.assertEqual(self.result()['remaining'],20)
        p['injuryVerifiedAt']=STAMP;self.fixtures[10]['date']='2026-10-31'
        self.opps['days'][0]['date']='2026-10-31';self.assertEqual(self.result()['remaining'],20)

    def setUp(self):
        self.team={'teamId':1,'roster':[player(1,0,['PG']),player(2,0,['PG']),player(3,0,['PG'],'IR')]}
        self.current={'updatedAt':STAMP,'projectionHistory':{'verifiedAt':STAMP,'players':{str(i):{'games':[history(n,gid=i)],'error':None}for i,n in [(1,20),(2,10),(3,100)]}}}
        self.fixtures={10:{'date':'2026-10-31'},11:{'date':'2026-10-31'}}
        self.opps={'games':3,'uncertain':False,'players':[{'playerId':i,'gameIds':[10]}for i in (1,2,3)],'days':[{'date':'2026-10-31','period':12,'availableSlots':['PG'],'lockedPlayerIds':[],'additionalTBD':False}]}
    def result(self):return project_team(self.current,{}, {'state':'current'},self.team,self.opps,self.fixtures)
    def test_all_games_projected_even_bench_and_ir(self):
        result=self.result();self.assertEqual(result['remaining'],20)
        players=result['days'][0]['players'];self.assertEqual([p['points']for p in players],[20,10,100]);self.assertEqual([p['selected']for p in players],[True,False,False])
    def test_tbd_unknown_samples_and_unsupported_locks(self):
        self.opps['uncertain']=True;self.assertIsNone(self.result()['remaining']);self.assertEqual(self.result()['confirmedRemaining'],20)
        self.current['projectionHistory']['players']['2']['games']=[]
        self.assertIsNone(self.result()['confirmedRemaining'])
        self.opps['days'][0]['availableSlots']=None;self.assertIsNone(self.result()['days'][0]['points'])
    def test_locked_slots_and_later_roster_membership(self):
        self.opps['days'][0].update(availableSlots=[],lockedPlayerIds=[1])
        self.assertEqual(self.result()['remaining'],0)
        self.team['roster'].remove(self.team['roster'][0]);self.opps['players'].pop(0)
        self.assertEqual(self.result()['remaining'],0)
    def test_stale_history_unknown_affiliations_and_no_future_games(self):
        self.current['projectionHistory']['verifiedAt']='2026-10-27T00:00:00Z'
        self.assertIsNone(self.result()['remaining'])
        self.current['projectionHistory']['verifiedAt']=STAMP
        self.opps['players'][0]['gameIds']=None;self.assertIsNone(self.result()['remaining'])
    def test_cup_dates_do_not_show_complete_daily_zero_or_final(self):
        self.opps['uncertain']=True;self.opps['days'][0]['additionalTBD']=True
        result=self.result()
        self.assertIsNone(result['days'][0]['points']);self.assertEqual(result['confirmedRemaining'],20)
        self.assertIsNone(result['remaining'])
    def test_started_game_scoring_cannot_be_silently_omitted_from_final(self):
        self.opps['inProgress']=1
        self.assertIsNone(self.result()['remaining']);self.assertEqual(self.result()['confirmedRemaining'],20)

    def test_mutation_protection(self):
        before=deepcopy((self.current,self.team,self.opps,self.fixtures));self.result()
        self.assertEqual((self.current,self.team,self.opps,self.fixtures),before)

if __name__=='__main__':unittest.main()
