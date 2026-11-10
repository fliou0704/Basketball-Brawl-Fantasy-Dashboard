"""Synthetic, credential-free live adapter contracts; no network."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch

import requests
import liveScoringAdapter as live
from espnFantasyCalendar import normalize as normalize_calendar,context

NOW=datetime(2026,10,31,18,tzinfo=timezone.utc)


def metadata():
    f=json.loads((Path(__file__).parent/'fixtures/fantasy_calendar_2027.json').read_text())
    ctx=context(f['league']);calendar=normalize_calendar(f['constants'],ctx)
    calendar['verifiedAt']='2026-10-30T12:00:00Z'
    return {'seasons':[{'season':2027,'fantasyCalendarContext':ctx,'fantasyCalendar':calendar}]}


def raw(period=12):
    def member(pid,slot,points):
        return {'playerId':pid,'lineupSlotId':slot,'playerPoolEntry':{'onTeamId':1 if pid<20 else 2,'appliedStatTotal':points,
            'player':{'id':pid,'fullName':str(pid),'proTeamId':1 if pid<20 else 2,'eligibleSlots':[0,11,12],
                'injuryStatus':'ACTIVE','stats':[{'statSourceId':0,'statSplitTypeId':5,'seasonId':2027,
                    'scoringPeriodId':period,'appliedTotal':points,'stats':{'40':22,'0':10}}]}}}
    def side(tid,players,total):
        return {'teamId':tid,'totalPoints':total-5,'totalPointsLive':total,'pointsByScoringPeriod':{str(period):total},
                'rosterForCurrentScoringPeriod':{'appliedStatTotal':total,'entries':players}}
    return {'id':123,'segmentId':0,'seasonId':2027,'scoringPeriodId':period,'status':{'currentMatchupPeriod':2,'latestScoringPeriod':period,'firstScoringPeriod':1,'finalScoringPeriod':167},
        'settings':{'scheduleSettings':json.loads((Path(__file__).parent/'fixtures/fantasy_calendar_2027.json').read_text())['league']['settings']['scheduleSettings'],'size':2,'scoringSettings':{'scoringType':'H2H_POINTS'},'rosterSettings':{'lineupSlotCounts':{'0':1,'12':1,'13':1}}},
        'teams':[{'id':1,'name':'One'},{'id':2,'name':'Two'}],
        'schedule':[{'id':7,'matchupPeriodId':2,'winner':'UNDECIDED','home':side(1,[member(10,0,20),member(11,12,9),member(12,13,8)],21),
                     'away':side(2,[member(20,0,30)],30)}]}


def nba(day='2026-10-31',name='STATUS_IN_PROGRESS',state='in',gid=456):
    return {'leagues':[{'id':'46'}],'events':[{'id':str(gid),'date':day+'T23:00:00Z','season':{'year':2027,'type':2},
        'status':{'type':{'name':name,'state':state,'completed':state=='post'},'displayClock':'3:15','period':4},
        'competitions':[{'type':{'id':'1'},'timeValid':True,'competitors':[{'id':'1','homeAway':'home'},{'id':'2','homeAway':'away'}]}]}]}


def response(data=None,status=200,etag='"v1"',headers=None):
    r=Mock(status_code=status,content=b'body' if status==200 else b'',headers={'ETag':etag,**(headers or {})})
    r.json.return_value=data
    return r


class NormalizationTests(unittest.TestCase):
    def setUp(self):self.meta=metadata();self.raw=raw()
    def norm(self):return live.normalize_league(self.raw,2027,123,self.meta)

    def test_official_totals_never_forced_to_player_sum(self):
        t=self.norm()['teams'][0]
        self.assertEqual((t['officialScore'],t['playerCreditedSum'],t['dailyDifference']),(21,20,1))
        self.assertEqual(t['officialScoreField'],'totalPointsLive')
        self.assertEqual([p['creditedPoints']for p in t['players']],[20,0,0])
        self.assertEqual([p['fantasyPoints']for p in t['players']],[20,9,8])

    def test_missing_live_total_uses_labelled_official_fallback(self):
        del self.raw['schedule'][0]['home']['totalPointsLive']
        t=self.norm()['teams'][0];self.assertEqual(t['officialScoreField'],'totalPoints');self.assertEqual(t['periodSumDifference'],-5)

    def test_no_stats_is_not_a_fabricated_appearance(self):
        e=self.raw['schedule'][0]['home']['rosterForCurrentScoringPeriod']['entries'][0]
        e['playerPoolEntry']['player']['stats']=[];e['playerPoolEntry']['appliedStatTotal']=0
        p=self.norm()['teams'][0]['players'][0]
        self.assertIsNone(p['played']);self.assertIsNone(p['statPoints']);self.assertFalse(p['hasActualStats'])

    def test_only_actual_current_period_stats_not_projections_or_history(self):
        p=self.raw['schedule'][0]['home']['rosterForCurrentScoringPeriod']['entries'][0]['playerPoolEntry']['player']
        p['stats'] += [dict(p['stats'][0],scoringPeriodId=11,appliedTotal=999),dict(p['stats'][0],statSourceId=1,appliedTotal=999),dict(p['stats'][0],statSplitTypeId=1,appliedTotal=999)]
        self.assertEqual(self.norm()['teams'][0]['players'][0]['statPoints'],20)

    def test_missing_partial_duplicate_and_nonfinite_data_rejected(self):
        mutations=[lambda r:r.pop('teams'),lambda r:r['schedule'][0].pop('away'),
            lambda r:r['schedule'][0]['home']['rosterForCurrentScoringPeriod'].update(entries=[]),
            lambda r:r['schedule'][0]['home'].update(totalPointsLive=float('nan')),
            lambda r:r['schedule'][0]['away']['rosterForCurrentScoringPeriod']['entries'][0]['playerPoolEntry'].update(onTeamId=1)]
        for mutate in mutations:
            self.raw=raw();mutate(self.raw)
            with self.subTest(mutate=mutate),self.assertRaises(live.AdapterError):self.norm()

    def test_calendar_mismatch_missing_unknown_slot_and_season_rejected(self):
        for change in ('calendar','week','season','slot'):
            self.raw=raw();self.meta=metadata()
            if change=='calendar':self.meta={}
            if change=='week':self.raw['status']['currentMatchupPeriod']=3
            if change=='season':self.raw['seasonId']=2026
            if change=='slot':self.raw['schedule'][0]['home']['rosterForCurrentScoringPeriod']['entries'][0]['lineupSlotId']=999
            with self.subTest(change=change),self.assertRaises(live.AdapterError):self.norm()

    def test_statuses_game_identity_and_ny_midnight(self):
        for name,state,want in [('STATUS_FINAL','post','completed'),('STATUS_IN_PROGRESS','in','in-progress'),('STATUS_POSTPONED','pre','postponed'),('STATUS_CANCELED','pre','canceled')]:
            self.assertEqual(live.normalize_games(nba(name=name,state=state),'2026-10-31',2027)['games'][0]['status'],want)
        value=nba();value['events'][0]['date']='2026-11-01T02:00:00Z'
        self.assertEqual(len(live.normalize_games(value,'2026-10-31',2027)['games']),1)
        value['events'][0]['competitions'][0]['type']['id']='39'
        self.assertEqual(live.normalize_games(value,'2026-10-31',2027)['games'],[])

    def test_empty_failed_and_duplicate_scoreboard(self):
        for value in ({}, {'events':[]},dict(nba(),events=nba()['events']*2)):
            with self.assertRaises(live.AdapterError):live.normalize_games(value,'2026-10-31',2027)
        self.assertEqual(live.normalize_games({'leagues':[1],'events':[]},'2026-10-31',2027)['games'],[])

    def test_missing_expected_fixture_fails_without_turning_into_zero(self):
        league=self.norm();m=metadata();m['nbaSchedules']={'2027':{'fixtures':[{'id':999,'date':league['date'],'regularSeason':True,'status':'scheduled'}]}}
        with self.assertRaises(live.AdapterError):live.assemble(league,{'games':[]},m)


    def test_known_historical_discrepancy_values_preserve_both_sources(self):
        side=self.raw['schedule'][0]['home'];side['totalPointsLive']=1467
        side['pointsByScoringPeriod']['12']=1467
        side['rosterForCurrentScoringPeriod']['entries'][0]['playerPoolEntry']['appliedStatTotal']=1471
        t=self.norm()['teams'][0]
        self.assertEqual((t['officialScore'],t['playerCreditedSum'],t['dailyDifference']),(1467,1471,-4))

    def test_week_rollover_and_stale_period_response(self):
        self.raw=raw(14);self.raw['status']['currentMatchupPeriod']=3
        self.raw['schedule'][0]['matchupPeriodId']=3
        self.assertEqual((self.norm()['week'],self.norm()['date']),(3,'2026-11-02'))
        self.raw['status']['latestScoringPeriod']=15
        with self.assertRaises(live.AdapterError):self.norm()

    def test_current_stat_nba_team_preserved_after_affiliation_change(self):
        e=self.raw['schedule'][0]['home']['rosterForCurrentScoringPeriod']['entries'][0]
        p=e['playerPoolEntry']['player'];p['proTeamId']=3;p['stats'][0]['proTeamId']=1
        value=live.assemble(self.norm(),live.normalize_games(nba(),'2026-10-31',2027),self.meta)
        p=value['teams'][0]['players'][0]
        self.assertEqual((p['proTeamId'],p['statProTeamId'],p['gameIds']),(3,1,[456]))


class TransportAndPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.output=Path(self.temp.name)/'live.json';self.meta=metadata()
    def run_adapter(self,answers,now=NOW):
        session=Mock();session.get.side_effect=answers
        client=live.Client(session,sleep=lambda _:None)
        result=live.run(self.output,self.meta,2027,123,client=client,now=now,credentials=('fake-swid','fake-s2'))
        return result,session
    def initial(self):return self.run_adapter([response(raw()),response(nba())])

    def test_initial_snapshot_and_two_requests_only(self):
        result,session=self.initial();self.assertTrue(result['changed']);self.assertEqual(result['requests'],2)
        for call in session.get.call_args_list:
            self.assertEqual(call.kwargs['timeout'],(10,35));self.assertFalse(call.kwargs['allow_redirects'])
        self.assertIsNone(session.get.call_args_list[1].kwargs['cookies'])
        text=self.output.read_text()+self.output.with_suffix('.json.state.json').read_text()
        self.assertNotIn('fake-s2',text);self.assertNotIn('fake-swid',text)

    def test_persisted_304_noop_keeps_snapshot_bytes_and_mtime(self):
        self.initial();before=self.output.read_bytes();modified=self.output.stat().st_mtime_ns
        result,session=self.run_adapter([response(status=304),response(status=304)],NOW+timedelta(minutes=5))
        self.assertFalse(result['changed']);self.assertEqual(result['notModified'],2)
        self.assertEqual(before,self.output.read_bytes());self.assertEqual(modified,self.output.stat().st_mtime_ns)
        self.assertIn('If-None-Match',session.get.call_args.kwargs['headers'])
        state=json.loads(self.output.with_suffix('.json.state.json').read_text());self.assertEqual(state['verifiedAt'],(NOW+timedelta(minutes=5)).isoformat())

    def test_unchanged_200_also_noop(self):
        self.initial();result,_=self.initial();self.assertFalse(result['changed'])

    def test_auth_failure_has_no_retry_or_secret_and_retains_last_good(self):
        self.initial();before=self.output.read_bytes();session=Mock();session.get.return_value=response(status=401)
        with self.assertRaisesRegex(live.AdapterError,'authentication'):
            live.run(self.output,self.meta,2027,123,client=live.Client(session),now=NOW+timedelta(minutes=11),credentials=('x','y'))
        self.assertEqual(session.get.call_count,1);self.assertEqual(self.output.read_bytes(),before)
        state=json.loads(self.output.with_suffix('.json.state.json').read_text());self.assertTrue(state['freshness']['stale'])

    def test_failure_in_second_endpoint_does_not_publish_first(self):
        self.initial();before=self.output.read_bytes();changed=raw();changed['schedule'][0]['home']['totalPointsLive']=55
        with self.assertRaises(live.AdapterError):self.run_adapter([response(changed),response({},status=200)])
        self.assertEqual(before,self.output.read_bytes())

    def test_retries_are_bounded_and_retry_after_not_bypassed(self):
        session=Mock();session.get.return_value=response(status=429,headers={'Retry-After':'90'});sleep=Mock()
        with self.assertRaises(live.AdapterError):live.Client(session,sleep).read('https://example.test',{},None,None,lambda x:x)
        self.assertEqual(session.get.call_count,1);sleep.assert_not_called()
        session.get.side_effect=[requests.Timeout('never disclose this'),response(status=503),response({'ok':True})]
        session.get.return_value=response({'ok':True});sleep.reset_mock()
        value=live.Client(session,sleep).read('https://example.test',{},None,None,lambda x:x)
        self.assertEqual(value['data'],{'ok':True});self.assertEqual(sleep.call_count,2)

    def test_exhausted_retries_and_orphan_304(self):
        for answers in ([requests.Timeout('sensitive detail')]*3,[response(status=304)]):
            session=Mock();session.get.side_effect=answers
            with self.assertRaises(live.AdapterError) as e:live.Client(session,lambda _:None).read('https://example.test',{},None,None,lambda x:x)
            self.assertNotIn('sensitive',str(e.exception));self.assertLessEqual(session.get.call_count,3)

    def test_rollover_changes_period_and_invalidates_day_etag(self):
        self.initial();result,session=self.run_adapter([response(raw(13)),response(nba('2026-11-01'))],NOW+timedelta(days=1))
        self.assertTrue(result['changed']);self.assertNotIn('If-None-Match',session.get.call_args.kwargs['headers'])
        self.assertEqual(json.loads(self.output.read_text())['date'],'2026-11-01')
        with self.assertRaisesRegex(live.AdapterError,'regress'):self.run_adapter([response(raw()),response(nba())],NOW+timedelta(days=1))
        self.assertEqual(json.loads(self.output.read_text())['scoringPeriod'],13)

    def test_changes_identify_score_player_and_status_and_allow_decreases(self):
        self.initial();r=raw();r['schedule'][0]['home']['totalPointsLive']=19
        r['schedule'][0]['home']['rosterForCurrentScoringPeriod']['entries'][0]['playerPoolEntry']['appliedStatTotal']=18
        self.run_adapter([response(r),response(nba(name='STATUS_FINAL',state='post'))])
        s=json.loads(self.output.read_text());self.assertEqual(s['changes']['players'],[10]);self.assertEqual(s['changes']['matchups'],[7])
        self.assertEqual(s['changes']['games'],[456]);self.assertEqual(s['teams'][0]['officialScore'],19)

    def test_injury_only_changes_are_identified(self):
        self.initial();r=raw()
        r['schedule'][0]['home']['rosterForCurrentScoringPeriod']['entries'][0]['playerPoolEntry']['player']['injuryStatus']='OUT'
        self.run_adapter([response(r),response(nba())])
        value=json.loads(self.output.read_text())
        self.assertEqual(value['changes']['players'],[10]);self.assertEqual(value['teams'][0]['officialScore'],21)

    def test_changed_calendar_cannot_reuse_cached_304(self):
        self.initial();before=self.output.read_bytes()
        self.meta['seasons'][0]['fantasyCalendarContext']['regularWeeks']=19
        with self.assertRaises(live.AdapterError):self.run_adapter([response(status=304),response(status=304)])
        self.assertEqual(before,self.output.read_bytes())

    def test_wrong_cache_shape_is_rejected_before_network(self):
        self.initial();self.output.with_suffix('.json.state.json').write_text('[]')
        session=Mock()
        with self.assertRaises(live.AdapterError):
            live.run(self.output,self.meta,2027,123,client=live.Client(session),now=NOW,credentials=('x','y'))
        session.get.assert_not_called()

    def test_lock_output_guard_and_atomic_replace_failure(self):
        with live.locked(self.output):
            with self.assertRaisesRegex(live.AdapterError,'Another'):self.initial()
        with self.assertRaises(live.AdapterError):live.safe_output(live.ROOT/'data/live.json')
        live.atomic(self.output,{'good':True});before=self.output.read_bytes()
        with patch('liveScoringAdapter.os.replace',side_effect=OSError('disk')):
            with self.assertRaises(OSError):live.atomic(self.output,{'good':False})
        self.assertEqual(before,self.output.read_bytes());self.assertFalse(list(self.output.parent.glob('*.tmp')))

    def test_invalid_cache_and_clock(self):
        self.output.write_text('{broken')
        with self.assertRaises(live.AdapterError):self.initial()
        self.assertEqual(self.output.read_text(),'{broken')
        with self.assertRaises(live.AdapterError):live.run(self.output,self.meta,2027,123,now=datetime(2026,10,31))
        self.assertTrue(live.freshness({},NOW)['stale'])
        self.assertTrue(live.freshness({'verifiedAt':(NOW+timedelta(minutes=1)).isoformat()},NOW)['stale'])


if __name__=='__main__':unittest.main()
