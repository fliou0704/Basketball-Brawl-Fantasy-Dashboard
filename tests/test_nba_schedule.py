"""Offline, bounded source/cache/status regressions, with a full 30-team fixture."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nbaSchedule import normalize, refresh, recent_status, wrapper_schedule, valid_cache, uncertainty, ScheduleError


def full_schedule():
    teams = {t:{'id':t,'abbrev':str(t),'proGamesByScoringPeriod':{}} for t in range(1,31)}
    for day in range(80):
        stamp = datetime(2026,10,20,23,tzinfo=timezone.utc)+timedelta(days=day*2)
        for pair in range(15):
            a,z=pair+1,30-pair
            g={'id':10000+day*15+pair,'date':int(stamp.timestamp()*1000),'homeProTeamId':a,'awayProTeamId':z,
               'scoringPeriodId':day*2+1,'statsOfficial':False,'validForLocking':True,'startTimeTBD':False}
            for tid in (a,z):teams[tid]['proGamesByScoringPeriod'].setdefault(str(day*2+1),[]).append(deepcopy(g))
    return {'settings':{'proTeams':list(teams.values())}}


def event(game, name='STATUS_SCHEDULED', state='pre', kind='1', date=None):
    return {'id':str(game['id']),'date':date or game['start'],'season':{'year':2027,'type':2},
            'status':{'type':{'name':name,'state':state,'completed':state=='post'}},
            'competitions':[{'type':{'id':kind},'timeValid':True,'competitors':[{'id':str(game['home'])},{'id':str(game['away'])}]}]}


class NBAScheduleTests(unittest.TestCase):
    def setUp(self):
        self.raw=full_schedule();self.now=datetime(2026,10,20,15,tzinfo=timezone.utc);self.calls=0

    def fetch(self,_):self.calls+=1;return self.raw
    def update(self,old=None,**kw):return refresh(old,2027,kw.pop('now',self.now),fetch=self.fetch,log=lambda _:None,**kw)

    def test_full_initialization_normalized_stable_ids_and_round_trip(self):
        value=self.update()
        self.assertTrue(valid_cache(value));self.assertEqual(len(value['fixtures']),1200)
        self.assertEqual(len(value['teams']),30)
        self.assertEqual(uncertainty(value)['1']['unassigned'],2)
        self.assertEqual(normalize(wrapper_schedule(value),2027)['fixtures'],value['fixtures'])

    def test_persisted_cache_daily_clock_force_and_rollover(self):
        value=self.update()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'metadata.json';path.write_text(json.dumps({'nbaSchedules':{'2027':value}}))
            old=json.loads(path.read_text())['nbaSchedules']['2027']
            self.assertEqual(self.update(old,now=self.now+timedelta(hours=23)),old)
            self.assertEqual(self.calls,1)
            self.update(old,now=self.now+timedelta(hours=24));self.assertEqual(self.calls,2)
            self.update(old,force=True);self.assertEqual(self.calls,3)
        other=deepcopy(value);other['season']=2026
        self.update(other);self.assertEqual(self.calls,4)

    def test_failure_partial_empty_and_failure_cooldown(self):
        old=self.update()
        for raw in [{},{'settings':{'proTeams':[]}}, {'settings':{'proTeams':self.raw['settings']['proTeams'][:29]}}]:
            self.raw=raw;failed=self.update(old,force=True)
            self.assertEqual(failed['fixtures'],old['fixtures']);self.assertEqual(failed['verifiedAt'],old['verifiedAt'])
            self.assertIn('lastError',failed)
        calls=self.calls;self.update(json.loads(json.dumps(failed)),now=self.now+timedelta(hours=3));self.assertEqual(self.calls,calls)
        def fail(_):raise ScheduleError('network unavailable')
        failed=refresh(old,2027,self.now+timedelta(days=1),fetch=fail,log=lambda _:None)
        self.assertEqual(failed['fixtures'],old['fixtures'])
        self.assertEqual(failed['verifiedAt'],old['verifiedAt'])
        initial=refresh(None,2027,self.now,fetch=fail,log=lambda _:None)
        self.assertNotIn('verifiedAt',initial)

    def test_duplicate_ids_and_one_sided_coverage_are_rejected(self):
        for mode in ['duplicate','one-sided','missing']:
            raw=full_schedule();entries=raw['settings']['proTeams'][0]['proGamesByScoringPeriod']['1']
            if mode=='duplicate':entries.append(deepcopy(entries[0]))
            else:entries.clear()
            with self.assertRaises(ScheduleError):normalize(raw,2027)

    def test_new_cup_fixture_and_future_time_date_changes(self):
        old=self.update();raw=wrapper_schedule(old)
        g={'id':99999,'date':int(datetime(2026,12,4,23,tzinfo=timezone.utc).timestamp()*1000),
           'homeProTeamId':1,'awayProTeamId':2,'scoringPeriodId':46,'statsOfficial':False,'validForLocking':True}
        for t in raw['settings']['proTeams']:
            if t['id']in(1,2):t['proGamesByScoringPeriod'].setdefault('46',[]).append(deepcopy(g))
        new=normalize(raw,2027,old)
        self.assertEqual(len(new['fixtures']),1201);self.assertEqual(uncertainty(new)['1']['unassigned'],1)
        for t in raw['settings']['proTeams']:
            for gs in t['proGamesByScoringPeriod'].values():
                for item in gs:
                    if item['id']==99999:item['date']+=86400000
        self.assertEqual(next(g for g in normalize(raw,2027,new)['fixtures']if g['id']==99999)['date'],'2026-12-05')

    def test_status_overlay_postponed_canceled_in_progress_and_cup_final(self):
        base=self.update();game=base['fixtures'][0]
        for name,state,expected in [('STATUS_POSTPONED','pre','postponed'),('STATUS_CANCELED','post','canceled'),
                                     ('STATUS_IN_PROGRESS','in','in-progress'),('STATUS_FINAL','post','completed')]:
            data={'leagues':[{}],'events':[event(g,name,state) if g['id']==game['id'] else event(g) for g in base['fixtures'] if g['date']==game['date']]}
            got=recent_status(base,self.now,fetch=lambda *_:data,log=lambda _:None)
            self.assertEqual(got['fixtures'][0]['status'],expected)
            self.assertEqual(base['fixtures'][0]['status'],'scheduled')
        data={'leagues':[{}],'events':[event(g,kind='39') if g['id']==game['id'] else event(g)for g in base['fixtures'] if g['date']==game['date']]}
        got=recent_status(base,self.now,fetch=lambda *_:data,log=lambda _:None)
        self.assertFalse(got['fixtures'][0]['regularSeason'])

    def test_history_not_rewritten_and_missing_source_does_not_cancel(self):
        old=self.update();old['fixtures'][0]['status']='completed'
        raw=wrapper_schedule(old);gid=old['fixtures'][0]['id']
        for t in raw['settings']['proTeams']:
            for gs in t['proGamesByScoringPeriod'].values():
                for g in gs:
                    if g['id']==gid:g['date']+=86400000
        with self.assertRaises(ScheduleError):normalize(raw,2027,old)
        empty=recent_status(old,self.now,fetch=lambda *_:{'leagues':[{}],'events':[]},log=lambda _:None)
        self.assertEqual(empty['fixtures'],old['fixtures'])

    def test_status_failure_and_timezone_boundary(self):
        old=self.update()
        def fail(*_):raise ScheduleError('outage')
        result=recent_status(old,self.now,fetch=fail,log=lambda _:None)
        self.assertEqual(result['fixtures'],old['fixtures']);self.assertIn('statusError',result)
        for invalid in (None,[],{'events':[]}):
            result=recent_status(old,self.now,fetch=lambda *_,value=invalid:value,log=lambda _:None)
            self.assertEqual(result['fixtures'],old['fixtures']);self.assertIn('statusError',result)
        with self.assertRaises(ScheduleError):
            refresh(old,2027,datetime(2026,10,20),fetch=self.fetch,log=lambda _:None)
        raw=full_schedule()
        for t in raw['settings']['proTeams']:
            for g in t['proGamesByScoringPeriod']['1']:g['date']+=3*3600000
        self.assertEqual(normalize(raw,2027)['fixtures'][0]['date'],'2026-10-20')

    def test_cancel_tombstone_and_unambiguous_future_id_replacement(self):
        old=self.update();old['fixtures'][-1]['status']='canceled'
        raw=wrapper_schedule(old)
        # Canceled source records may disappear, but the cached tombstone stays.
        out=normalize(raw,2027,old,now=self.now)
        self.assertEqual(out['fixtures'][-1]['status'],'canceled')
        old=self.update();raw=wrapper_schedule(old);gid=old['fixtures'][-1]['id']
        for t in raw['settings']['proTeams']:
            for gs in t['proGamesByScoringPeriod'].values():
                for g in gs:
                    if g['id']==gid:g['id']=999999
        out=normalize(raw,2027,old,now=self.now)
        tombstone=next(g for g in out['fixtures']if g['id']==gid)
        self.assertEqual(tombstone['replacedBy'],999999);self.assertFalse(tombstone['regularSeason'])
        self.assertTrue(valid_cache(dict(out,verifiedAt=self.now.isoformat())))

    def test_historical_parser_extras_are_frozen_and_never_coverage_evidence(self):
        raw=full_schedule();g=deepcopy(raw['settings']['proTeams'][0]['proGamesByScoringPeriod']['1'][0]);g['id']=99999
        for t in raw['settings']['proTeams']:
            if t['id']in(g['homeProTeamId'],g['awayProTeamId']):t['proGamesByScoringPeriod']['1'].append(deepcopy(g))
        value=normalize(raw,2027,parser_only=True)
        self.assertFalse(value['publishedComplete']);self.assertFalse(valid_cache(dict(value,verifiedAt=self.now.isoformat())))
        frozen=refresh(dict(value,verifiedAt=self.now.isoformat()),2027,self.now+timedelta(days=100),parser_only=True,
                       fetch=lambda _:self.fail('frozen historical parser must not fetch'),log=lambda _:None)
        self.assertEqual(value['fixtures'],frozen['fixtures'])

    def test_preseason_and_postseason_are_excluded_from_known_regular_window(self):
        raw=full_schedule()
        for day in [datetime(2026,10,1,23,tzinfo=timezone.utc),datetime(2027,5,1,23,tzinfo=timezone.utc)]:
            g=deepcopy(raw['settings']['proTeams'][0]['proGamesByScoringPeriod']['1'][0]);g.update(id=int(day.timestamp()),date=int(day.timestamp()*1000))
            for t in raw['settings']['proTeams']:
                if t['id']in(g['homeProTeamId'],g['awayProTeamId']):t['proGamesByScoringPeriod'].setdefault('200',[]).append(deepcopy(g))
        self.assertEqual(len(normalize(raw,2027)['fixtures']),1200)


if __name__=='__main__':unittest.main()
